"""Local SQLite store: chat, loudness, gaps, segments, jobs. Restart-safe.

Raw chat never leaves this file except as a small sample attached to a
candidate (token policy: never send raw logs to a model).
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

from .states import check_local

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS messages(
  id INTEGER PRIMARY KEY, channel TEXT NOT NULL, ts REAL NOT NULL,
  user TEXT NOT NULL, text TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS messages_ch_ts ON messages(channel, ts);
CREATE TABLE IF NOT EXISTS loudness(
  channel TEXT NOT NULL, ts REAL NOT NULL, lufs REAL NOT NULL,
  PRIMARY KEY(channel, ts));
CREATE TABLE IF NOT EXISTS gaps(
  id INTEGER PRIMARY KEY, channel TEXT NOT NULL, source TEXT NOT NULL,
  start_ts REAL NOT NULL, end_ts REAL, reason TEXT);
CREATE TABLE IF NOT EXISTS jobs(
  id TEXT PRIMARY KEY, channel TEXT NOT NULL, stage TEXT NOT NULL,
  start_ts REAL NOT NULL, end_ts REAL NOT NULL, trigger_ts REAL NOT NULL,
  score REAL NOT NULL, data TEXT NOT NULL DEFAULT '{}',
  dedupe_key TEXT, attempts INTEGER NOT NULL DEFAULT 0, last_error TEXT,
  created_at REAL NOT NULL, updated_at REAL NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS jobs_dedupe ON jobs(dedupe_key) WHERE dedupe_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS jobs_stage ON jobs(stage);
CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY, v TEXT NOT NULL);
"""


@dataclass
class Job:
    id: str
    channel: str
    stage: str
    start_ts: float
    end_ts: float
    trigger_ts: float
    score: float
    data: dict
    dedupe_key: str | None
    attempts: int
    last_error: str | None


class _LockedDB:
    """One sqlite connection shared by the event loop, executor and capture threads.
    Every call holds a lock: unsynchronised use raised "cannot commit - no transaction
    is active" with 3 live captures (2026-11-21)."""

    def __init__(self, conn: sqlite3.Connection):
        self._c, self._lock = conn, threading.RLock()

    def _call(self, name, *a):
        with self._lock:
            out = getattr(self._c, name)(*a)
            # materialise cursors inside the lock so rows are read safely
            return _Rows(out.fetchall(), out.lastrowid, out.rowcount) if isinstance(out, sqlite3.Cursor) else out

    def execute(self, *a): return self._call("execute", *a)
    def executemany(self, *a): return self._call("executemany", *a)
    def executescript(self, *a): return self._call("executescript", *a)
    def commit(self): return self._call("commit")
    def close(self): return self._call("close")


class _Rows(list):
    def __init__(self, rows, lastrowid, rowcount):
        super().__init__(rows)
        self.lastrowid, self.rowcount = lastrowid, rowcount

    def fetchall(self): return list(self)
    def fetchone(self): return self[0] if self else None


class Store:
    def __init__(self, path: Path | str):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = _LockedDB(sqlite3.connect(str(path), check_same_thread=False))
        self.db.executescript(SCHEMA)

    # chat / signals
    def add_messages(self, rows: Iterable[tuple[str, float, str, str]]) -> None:
        self.db.executemany("INSERT INTO messages(channel, ts, user, text) VALUES(?,?,?,?)", rows)
        self.db.commit()

    def messages(self, channel: str, start: float, end: float) -> list[tuple[float, str, str]]:
        return self.db.execute(
            "SELECT ts, user, text FROM messages WHERE channel=? AND ts>=? AND ts<? ORDER BY ts",
            (channel, start, end)).fetchall()

    def add_loudness(self, channel: str, rows: Iterable[tuple[float, float]]) -> None:
        self.db.executemany("INSERT OR REPLACE INTO loudness VALUES(?,?,?)",
                            ((channel, t, v) for t, v in rows))
        self.db.commit()

    def open_gap(self, channel: str, source: str, ts: float, reason: str) -> int:
        cur = self.db.execute("INSERT INTO gaps(channel, source, start_ts, reason) VALUES(?,?,?,?)",
                              (channel, source, ts, reason))
        self.db.commit()
        return cur.lastrowid

    def close_gap(self, gap_id: int, ts: float) -> None:
        self.db.execute("UPDATE gaps SET end_ts=? WHERE id=?", (ts, gap_id))
        self.db.commit()

    def gaps(self, channel: str) -> list[tuple]:
        return self.db.execute("SELECT source, start_ts, end_ts, reason FROM gaps WHERE channel=?",
                               (channel,)).fetchall()

    def prune(self, before_ts: float) -> None:
        self.db.execute("DELETE FROM messages WHERE ts<?", (before_ts,))
        self.db.execute("DELETE FROM loudness WHERE ts<?", (before_ts,))
        self.db.commit()

    # jobs
    def create_job(self, job_id: str, channel: str, start: float, end: float, trigger: float,
                   score: float, data: dict, dedupe_key: str | None) -> bool:
        now = time.time()
        try:
            self.db.execute(
                "INSERT INTO jobs(id, channel, stage, start_ts, end_ts, trigger_ts, score, data,"
                " dedupe_key, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (job_id, channel, "detected", start, end, trigger, score, json.dumps(data),
                 dedupe_key, now, now))
        except sqlite3.IntegrityError:
            return False  # duplicate moment (dedupe)
        self.db.commit()
        return True

    def _row(self, r) -> Job:
        return Job(r[0], r[1], r[2], r[3], r[4], r[5], r[6], json.loads(r[7]), r[8], r[9], r[10])

    _COLS = "id, channel, stage, start_ts, end_ts, trigger_ts, score, data, dedupe_key, attempts, last_error"

    def job(self, job_id: str) -> Job:
        r = self.db.execute(f"SELECT {self._COLS} FROM jobs WHERE id=?", (job_id,)).fetchone()
        if r is None:
            raise KeyError(job_id)
        return self._row(r)

    def jobs_in(self, stage: str) -> Iterator[Job]:
        for r in self.db.execute(f"SELECT {self._COLS} FROM jobs WHERE stage=? ORDER BY created_at",
                                 (stage,)).fetchall():
            yield self._row(r)

    def recent_jobs(self, channel: str, before_ts: float, limit: int = 60) -> list[Job]:
        """This channel's earlier candidates (newest first), for flashback matching."""
        return [self._row(r) for r in self.db.execute(
            f"SELECT {self._COLS} FROM jobs WHERE channel=? AND trigger_ts<? ORDER BY trigger_ts DESC LIMIT ?",
            (channel, before_ts, limit)).fetchall()]

    def triggers_between(self, channel: str, lo: float, hi: float) -> dict[str, float]:
        """{job_id: trigger_ts} for this channel's candidates in [lo, hi]."""
        rows = self.db.execute("SELECT id, trigger_ts FROM jobs WHERE channel=? AND trigger_ts BETWEEN ? AND ?",
                               (channel, lo, hi)).fetchall()
        return {r[0]: float(r[1]) for r in rows}

    def recent_scores(self, channel: str, before_ts: float, limit: int = 200) -> list[float]:
        """Detector scores of this channel's earlier candidates (stream baseline for the 0-100 score)."""
        rows = self.db.execute("SELECT score FROM jobs WHERE channel=? AND trigger_ts<? "
                               "ORDER BY trigger_ts DESC LIMIT ?", (channel, before_ts, limit)).fetchall()
        return [float(r[0]) for r in rows]

    def advance(self, job_id: str, dst: str, data_update: dict | None = None,
                error: str | None = None) -> Job:
        job = self.job(job_id)
        check_local(job.stage, dst)
        data = {**job.data, **(data_update or {})}
        self.db.execute("UPDATE jobs SET stage=?, data=?, last_error=?, updated_at=? WHERE id=?",
                        (dst, json.dumps(data), error, time.time(), job_id))
        self.db.commit()
        return self.job(job_id)

    def reset_for_revision(self, job_id: str, data_update: dict) -> Job:
        """Revise loop only: send an uploaded/qa job back to `judged` to re-render."""
        job = self.job(job_id)
        data = {**job.data, **data_update}
        self.db.execute("UPDATE jobs SET stage='judged', data=?, attempts=0, updated_at=? WHERE id=?",
                        (json.dumps(data), time.time(), job_id))
        self.db.commit()
        return self.job(job_id)

    def patch_data(self, job_id: str, data_update: dict) -> Job:
        job = self.job(job_id)
        self.db.execute("UPDATE jobs SET data=?, updated_at=? WHERE id=?",
                        (json.dumps({**job.data, **data_update}), time.time(), job_id))
        self.db.commit()
        return self.job(job_id)

    def record_failure(self, job_id: str, error: str) -> int:
        self.db.execute("UPDATE jobs SET attempts=attempts+1, last_error=?, updated_at=? WHERE id=?",
                        (error, time.time(), job_id))
        self.db.commit()
        return self.job(job_id).attempts

    def kv_get(self, k: str, default=None):
        r = self.db.execute("SELECT v FROM kv WHERE k=?", (k,)).fetchone()
        return json.loads(r[0]) if r else default

    def kv_set(self, k: str, v) -> None:
        self.db.execute("INSERT OR REPLACE INTO kv VALUES(?,?)", (k, json.dumps(v)))
        self.db.commit()
