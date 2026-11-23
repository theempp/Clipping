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

from . import __version__, brain
from .capture.buffer import capture_commands, parse_ebur128_line, prune
from .clock import Clock
from .config import Settings, env
from .detector.brain import apply_brain
from .detector.deadair import DeadAirGate
from .detector.spike import SpikeDetector
from .gpu import snapshot as gpu_snapshot
from .ingest import status as st
from .ingest import viewer_clips
from .ingest.kick_chat import run_kick_pusher
from .ingest.twitch_irc import run_twitch_chat
from .pipeline import Pipeline
from .power import keep_awake
from .roster import pick_captures
from .store import Store


def stream_fields(info: dict[str, dict]) -> dict:
    """Heartbeat keys the dashboard rail reads: viewers, live_since and game per channel key."""
    viewers = {k: v["viewers"] for k, v in info.items() if v.get("viewers") is not None}
    since = {k: v["started_at"] for k, v in info.items() if v.get("started_at")}
    games = {k: v["game"] for k, v in info.items() if v.get("game")}
    return {"viewers": viewers, "live_since": since, "games": games}


def streamer_rows(channels) -> list[dict]:
    """streamers rows for the active roster; inserted with ignore-duplicates, so existing rows stay."""
    return [{"slug": c.streamer, "display_name": c.name or c.login,
             "twitch_login": c.login if c.platform == "twitch" else None,
             "kick_slug": c.login if c.platform == "kick" else None} for c in channels]


def roster_fields(channels) -> dict:
    """Active roster for the dashboard rail: channel key -> group (core | gta6_only)."""
    return {"roster": {c.key: c.group for c in channels}}

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
                try:  # this thread must keep draining ffmpeg's stderr or capture stalls
                    self.on_loud(anchor + hit[0], hit[1])
                except Exception as e:  # noqa: BLE001
                    log.warning("loudness sink failed for %s: %s", self.login, e)
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
        self.det = {c.key: self._detector(c) for c in settings.channels}
        self.live: set[str] = set()
        # Wake Up (D055): with Supabase the dashboard switch decides; offline runs stay on.
        self.awake: bool = supabase is None
        self.caps: dict[str, Capture] = {}
        self._gap: dict[str, int] = {}
        self._pending: list[tuple] = []
        self._lock = threading.Lock()

    def _detector(self, c) -> SpikeDetector:
        """Fixed weights, or this streamer's own brain when features.brain is on (D089)."""
        if not self.s.features.brain:
            return SpikeDetector(c.key, c.detector, c.reaction_weights)
        b = brain.load(self.s.state_dir(c), c.streamer)
        return SpikeDetector(c.key, brain.apply(b, c.detector), c.reaction_weights,
                             lift=b.chat_word_lift if not b.learning else None)

    def _note_stream(self, c) -> None:
        if self.s.features.brain:
            d = self.s.state_dir(c)
            if d.exists():  # no folder = streamer has no brain yet; never create one silently
                brain.save(brain.note_stream(brain.load(d, c.streamer)), d)

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
        self._tw = (http, tw_tok)  # shared with the viewer-clip poller
        kk_tok = (st.AppToken(st.KICK_TOKEN_URL, env("KICK_CLIENT_ID", required=True),
                              env("KICK_CLIENT_SECRET", required=True), http) if kk else None)
        while True:
            try:
                info = {}
                if tw:
                    info.update({f"twitch:{k}": v for k, v in
                                 st.twitch_streams(http, tw_tok, [c.login for c in tw]).items()})
                if kk:
                    info.update({f"kick:{k}": v for k, v in
                                 st.kick_streams(http, kk_tok, [c.login for c in kk]).items()})
                self.stream_info = info
                permitted = {c.key for c in self.s.channels if self.pipe.rights.permit(c.streamer)}
                pick = pick_captures(self.s.channels, info, permitted, self.s.max_channels, self.s.gta6)
                for key, b in pick.boost.items():
                    self.det[key].boost = b
                if pick.skipped:
                    log.info("capture cap %d reached; not capturing %s", self.s.max_channels, pick.skipped)
                self.live = pick.capture if self.awake else set()
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
                if cap is None:  # new stream
                    self._note_stream(c)
                    if self.s.features.dead_air_gate:  # show_start again
                        det.gate = DeadAirGate(self.s.dead_air)

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
                    m.features["game"] = getattr(self, "stream_info", {}).get(key, {}).get("game")
                    job = self.pipe.on_moment(m)
                    log.info("moment %s score %.2f -> job %s", key, m.peak_score, job)
            await asyncio.sleep(max(0.0, 1.0 - (self.clock.now() - now)))

    def poll_viewer_clips_once(self, now: float, fetch=None) -> int:
        """Viewer clips in the last 15 min -> badge matching jobs + labels (features.viewer_clips)."""
        http, tok = getattr(self, "_tw", (None, None))
        if fetch is None and tok is None:
            return 0
        seen = self.__dict__.setdefault("_viewer_seen", set())
        n = 0
        for c in self.s.channels:
            info = getattr(self, "stream_info", {}).get(c.key) or {}
            if c.platform != "twitch" or c.key not in self.live or not info.get("user_id"):
                continue
            clips = (fetch or (lambda b, s, e: viewer_clips.fetch_clips(
                http, tok.client_id, tok.get(), b, s, e)))(info["user_id"], now - 900, now)
            clips = [x for x in clips if x.clip_id not in seen]
            if not clips:
                continue
            seen.update(x.clip_id for x in clips)
            trig = self.store.triggers_between(c.key, now - 900 - 60, now)
            by_job, rows = viewer_clips.label_rows(clips, trig, c.streamer)
            for jid, ids in by_job.items():
                job = self.store.job(jid)
                badges = sorted(set(job.data.get("badges", [])) | {"viewers_clipped"})
                self.store.patch_data(jid, {"badges": badges,
                                            "viewer_clip_ids": sorted(set(job.data.get("viewer_clip_ids", [])) | set(ids))})
            if self.sb is not None and rows:
                try:
                    self.sb.insert("clip_labels", rows, on_conflict="streamer,job_id,signal",
                                   ignore_duplicates=True)
                except Exception as e:  # noqa: BLE001 - labels must never block capture
                    log.warning("clip_labels write failed: %s", e)
            n += len(clips)
        return n

    async def poll_viewer_clips(self):
        while True:
            try:
                self.poll_viewer_clips_once(self.clock.now())
            except Exception as e:  # noqa: BLE001
                log.warning("viewer-clip poll failed: %s", e)
            await asyncio.sleep(60)

    async def every(self, seconds: float, fn, name: str):
        loop = asyncio.get_running_loop()
        while True:
            try:
                await loop.run_in_executor(None, fn)
            except Exception as e:  # noqa: BLE001
                log.warning("%s failed: %s", name, e)
            await asyncio.sleep(seconds)

    def sync_brain(self):
        """Apply Zo's Streamer Brain sliders and words (dashboard Settings) to each channel's detector.
        Always starts from the channel's config values, so removing a brain row restores them."""
        streamers = {r["id"]: r["slug"] for r in self.sb.select("streamers", select="id,slug")}
        brains = {streamers.get(r["streamer_id"]): r for r in self.sb.select("streamer_brain", select="*")}
        applied = {}
        for c in self.s.channels:
            b = brains.get(c.streamer)
            params, reactions = apply_brain(c.detector, c.reaction_weights,
                                            b and b.get("weights"), b and b.get("words"))
            self.det[c.key].retune(params, reactions)
            if b:
                applied[c.key] = b.get("updated_at")
        if applied != getattr(self, "_brain_seen", None):
            log.info("streamer brain applied: %s", applied or "none (config values)")
            self._brain_seen = applied

    def sync_awake(self):
        """Read the Wake Up switch. Asleep = stop captures and detection; jobs already
        rendering, in review or publishing keep going. Read errors keep the last value."""
        try:
            on = self.sb.awake()
        except Exception as e:  # noqa: BLE001
            log.warning("wake read failed: %s", e)
            return
        if on is None or on == self.awake:
            return
        self.awake = on
        log.info("dashboard switched %s", "awake" if on else "asleep")
        if not on:
            self.live = set()
            self._sync_captures()

    def heartbeat(self):
        if self.sb is None:
            return
        self.sync_awake()
        depth = {s: n for s, n in self.store.db.execute(
            "SELECT stage, count(*) FROM jobs WHERE stage NOT IN ('uploaded','dropped') GROUP BY stage")}
        self.sb.heartbeat(WORKER_ID, {"version": __version__, "awake": self.awake, "live": sorted(self.live),
                                      "capturing": sorted(k for k, c in self.caps.items() if c.alive()),
                                      "queue": depth, "clock_drift_s": round(self.clock.check_drift(), 3),
                                      **stream_fields(getattr(self, "stream_info", {})),
                                      **roster_fields(self.s.channels),
                                      **({"gpu": g} if (g := gpu_snapshot()) else {})})

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
        if self.publisher is not None and not self.s.features.dry_run:
            tasks.append(self.every(30, self.publisher.run_once, "publisher"))
        if self.sb is not None:
            tasks.append(self.every(60, self.sync_brain, "streamer brain"))
        if self.s.features.viewer_clips:
            tasks.append(self.poll_viewer_clips())
        if self.s.features.clip_that and self.sb is not None:
            tasks.append(self.every(5, lambda: self.pipe.take_clip_requests(self.clock.now(), self.live),
                                    "clip_that"))
        tw = [c.login for c in self.s.channels if c.platform == "twitch"]
        if tw:
            tasks.append(run_twitch_chat(tw, self._on_chat, self.clock.now, self._on_gap))
        rooms = {str(k): v.lower() for k, v in self.s.extra.get("kick_chatrooms", {}).items()}
        if rooms and env("KICK_PUSHER_KEY"):
            tasks.append(run_kick_pusher(env("KICK_PUSHER_KEY"), rooms, self._on_chat,
                                         self.clock.now, self._on_gap))
        if self.sb is not None:
            try:  # the dashboard rail lists streamers from this table
                self.sb.insert("streamers", streamer_rows(self.s.channels), on_conflict="slug",
                               ignore_duplicates=True)
            except Exception as e:  # noqa: BLE001
                log.warning("streamer sync failed: %s", e)
            self.sync_awake()
        with keep_awake():
            await asyncio.gather(*tasks)
