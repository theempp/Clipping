"""Live runner: everything that runs while the PC is on (D013).

Loops: status poll (60 s), capture per live permitted channel, chat, detector
tick (1 s), pipeline (2 s), revisions (30 s), publisher (30 s), heartbeat
(15 s), prune (60 s). PC sleep is blocked only while a channel is captured.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import subprocess
import threading
import time

import httpx

from . import __version__
from .capture.buffer import capture_commands, parse_ebur128_line, prune
from .clock import Clock
from .config import Settings, env
from .detector.spike import SpikeDetector
from .ingest import status as st
from .ingest.kick_chat import run_kick_pusher
from .ingest.twitch_irc import run_twitch_chat
from .pipeline import Pipeline
from .power import keep_awake
from .store import Store

log = logging.getLogger(__name__)
WORKER_ID = os.environ.get("CLIP_WORKER_ID", "pc-main")


class Capture:
    """streamlink | ffmpeg for one channel; loudness read from ffmpeg stderr."""

    def __init__(self, platform: str, login: str, out_dir, clock: Clock, on_loud, on_exit):
        self.platform, self.login, self.out_dir, self.clock = platform, login, out_dir, clock
        self.on_loud, self.on_exit = on_loud, on_exit
        self.procs: list[subprocess.Popen] = []

    def start(self) -> None:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        sl_cmd, ff_cmd = capture_commands(self.platform, self.login, self.out_dir,
                                          env("STREAMLINK_BIN", "streamlink"), env("FFMPEG_BIN", "ffmpeg"))
        sl = subprocess.Popen(sl_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        ff = subprocess.Popen(ff_cmd, stdin=sl.stdout, stderr=subprocess.PIPE, text=True,
                              stdout=subprocess.DEVNULL)
        sl.stdout.close()
        self.procs = [sl, ff]
        anchor = self.clock.now()
        threading.Thread(target=self._read, args=(ff, anchor), daemon=True).start()

    def _read(self, ff: subprocess.Popen, anchor: float) -> None:
        last = -1
        for line in ff.stderr:
            hit = parse_ebur128_line(line)
            if hit and int(hit[0]) != last:
                last = int(hit[0])
                self.on_loud(anchor + hit[0], hit[1])
        self.on_exit()

    def alive(self) -> bool:
        return bool(self.procs) and all(p.poll() is None for p in self.procs)

    def stop(self) -> None:
        for p in self.procs:
            with contextlib.suppress(Exception):
                p.terminate()


class LiveRunner:
    def __init__(self, settings: Settings, store: Store, pipeline: Pipeline, publisher=None,
                 supabase=None):
        self.s, self.store, self.pipe, self.publisher, self.sb = settings, store, pipeline, publisher, supabase
        self.clock = Clock()
        self.det = {c.key: SpikeDetector(c.key, c.detector, c.reaction_weights) for c in settings.channels}
        self.live: set[str] = set()
        self.caps: dict[str, Capture] = {}
        self._gap: dict[str, int] = {}
        self._pending: list[tuple] = []
        self._lock = threading.Lock()

    # signal sinks (chat callbacks run on the event loop; loudness on capture threads)
    def _on_chat(self, ts, msg):
        for c in self.s.channels:
            if c.login == msg.channel and c.key in self.live:
                self.det[c.key].add_message(ts, msg.user, msg.text)
                with self._lock:
                    self._pending.append((c.key, ts, msg.user, msg.text))

    def _on_gap(self, login, start, end, reason):
        for c in self.s.channels:
            if c.login == login:
                gid = self.store.open_gap(c.key, "chat", start, reason)
                if end is not None:
                    self.store.close_gap(gid, end)

    async def poll_status(self):
        http = httpx.Client(timeout=20)
        tw = [c for c in self.s.channels if c.platform == "twitch"]
        kk = [c for c in self.s.channels if c.platform == "kick"]
        tw_tok = (st.AppToken(st.TWITCH_TOKEN_URL, env("TWITCH_CLIENT_ID", required=True),
                              env("TWITCH_CLIENT_SECRET", required=True), http) if tw else None)
        kk_tok = (st.AppToken(st.KICK_TOKEN_URL, env("KICK_CLIENT_ID", required=True),
                              env("KICK_CLIENT_SECRET", required=True), http) if kk else None)
        while True:
            try:
                live = {}
                if tw:
                    live.update({f"twitch:{k}": v for k, v in
                                 st.twitch_live(http, tw_tok, [c.login for c in tw]).items()})
                if kk:
                    live.update({f"kick:{k}": v for k, v in
                                 st.kick_live(http, kk_tok, [c.login for c in kk]).items()})
                permitted = {c.key for c in self.s.channels if self.pipe.rights.permit(c.streamer)}
                self.live = {k for k, v in live.items() if v and k in permitted}
                self._sync_captures()
            except Exception as e:  # noqa: BLE001
                log.warning("status poll failed: %s", e)
            await asyncio.sleep(60)

    def _sync_captures(self):
        chans = {c.key: c for c in self.s.channels}
        for key in list(self.caps):
            if key not in self.live:
                self.caps.pop(key).stop()
        for key in self.live:
            cap = self.caps.get(key)
            if cap is None or not cap.alive():
                c = chans[key]
                det = self.det[key]

                def on_loud(ts, v, key=key, det=det):
                    det.add_loudness(ts, v)
                    self.store.add_loudness(key, [(ts, v)])

                def on_exit(key=key):
                    self._gap[key] = self.store.open_gap(key, "video", self.clock.now(), "capture exited")

                cap = Capture(c.platform, c.login, self.s.buffer_dir / key.replace(":", "_"),
                              self.clock, on_loud, on_exit)
                cap.start()
                if key in self._gap:
                    self.store.close_gap(self._gap.pop(key), self.clock.now())
                self.caps[key] = cap

    async def tick_loop(self):
        while True:
            now = self.clock.now()
            with self._lock:
                rows, self._pending = self._pending, []
            if rows:
                self.store.add_messages(rows)
            for key in self.live:
                m = self.det[key].tick(now)
                if m:
                    job = self.pipe.on_moment(m)
                    log.info("moment %s score %.2f -> job %s", key, m.peak_score, job)
            await asyncio.sleep(max(0.0, 1.0 - (self.clock.now() - now)))

    async def every(self, seconds: float, fn, name: str):
        loop = asyncio.get_running_loop()
        while True:
            try:
                await loop.run_in_executor(None, fn)
            except Exception as e:  # noqa: BLE001
                log.warning("%s failed: %s", name, e)
            await asyncio.sleep(seconds)

    def heartbeat(self):
        if self.sb is None:
            return
        depth = {s: n for s, n in self.store.db.execute(
            "SELECT stage, count(*) FROM jobs WHERE stage NOT IN ('uploaded','dropped') GROUP BY stage")}
        self.sb.heartbeat(WORKER_ID, {"version": __version__, "live": sorted(self.live),
                                      "capturing": sorted(k for k, c in self.caps.items() if c.alive()),
                                      "queue": depth, "clock_drift_s": round(self.clock.check_drift(), 3)})

    def prune(self):
        now = self.clock.now()
        for c in self.s.channels:
            d = self.s.buffer_dir / c.key.replace(":", "_")
            if d.exists():
                prune(d, now)
        self.store.prune(now - 900)

    async def run(self):
        tasks = [self.poll_status(), self.tick_loop(),
                 self.every(2, self.pipe.run_once, "pipeline"),
                 self.every(30, self.pipe.process_revisions, "revisions"),
                 self.every(15, self.heartbeat, "heartbeat"),
                 self.every(60, self.prune, "prune")]
        if self.publisher is not None:
            tasks.append(self.every(30, self.publisher.run_once, "publisher"))
        tw = [c.login for c in self.s.channels if c.platform == "twitch"]
        if tw:
            tasks.append(run_twitch_chat(tw, self._on_chat, self.clock.now, self._on_gap))
        rooms = {str(k): v.lower() for k, v in self.s.extra.get("kick_chatrooms", {}).items()}
        if rooms and env("KICK_PUSHER_KEY"):
            tasks.append(run_kick_pusher(env("KICK_PUSHER_KEY"), rooms, self._on_chat,
                                         self.clock.now, self._on_gap))
        with keep_awake():
            await asyncio.gather(*tasks)
