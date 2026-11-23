"""Paste-a-link clip creation (D115, pending zo).

zo pastes a Twitch/Kick/YouTube/X link in the dashboard -> `link_jobs` row (request_link_clips RPC)
-> this runner, on the PC: probe (yt-dlp -J) -> download (yt-dlp, optional range) -> chat replay when
there is one (Twitch VOD via TwitchDownloaderCLI) -> detect (chat + audio, or audio only) -> the normal
Pipeline: transcribe -> Grok judge -> render -> clip-qa -> Supabase `pending_review`.
Every clip still needs zo's approval in Review; nothing here posts.

Times: moments live on the source's real clock (VOD start epoch + offset), so `moment_at` in Review
is the real stream time and clips already cut live from the same moment are skipped.
Each link gets its own SQLite store (renders and caches stay in the shared work dir), so offsets
from two links can never collide with each other or with live jobs.

Full-frame IRL: `full_frame` renders the channel with no split layout, i.e. the face-tracked full
frame path in render/ (track=True). The MediaPipe tracker work plugs in there, not here.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import re
import subprocess
import time
from dataclasses import dataclass, replace
from pathlib import Path
from statistics import mean, pstdev

from .config import Channel, Settings, env
from .detector.replay import load_twitchdownloader_chat, replay
from .detector.spike import Moment
from .dryrun import vod_extractor, vod_loudness
from .pipeline import Pipeline
from .remote.rights import RightsGate
from .store import Store

log = logging.getLogger(__name__)

SHORT_SOURCE_S = 90.0       # a source this short is one moment: zo picked it, the judge only trims
MAX_SPAN_S = 8 * 3600       # same cap as the link_jobs check constraint
LIVE_DUP_S = 45.0           # a moment this close to a clip already made from the live stream is skipped
GROK_EST_USD = 0.0025       # per judgment (grok-4.20 non-reasoning); the dashboard shows the estimate


# ---------- link parsing (same rules as public.link_key and dashboard/lib/links.ts) ----------
@dataclass(frozen=True)
class LinkRef:
    platform: str       # twitch | kick | youtube | x
    kind: str           # vod | clip | video
    id: str
    key: str            # canonical duplicate key, equals public.link_key(url)
    login: str | None   # channel login when the URL carries it


_UUID = r"[0-9a-fA-F-]{36}"


def parse_link(url: str) -> LinkRef | None:
    u = (url or "").strip()
    if not re.match(r"^https://", u, re.I) or len(u) > 500:
        return None
    u = re.sub(r"^https://", "", u, flags=re.I)
    first = u.split("/", 1)[0]
    host = first.split("?", 1)[0].lower()
    if "@" in host or ":" in host:
        return None
    host = re.sub(r"^(www|m|mobile)\.", "", host)
    rest = u[len(first):]
    q = rest.split("?", 1)[1] if "?" in rest else ""
    path = rest.split("?", 1)[0].split("#", 1)[0]

    def ref(platform, kind, id_, login=None):
        key = f"{platform}:{kind}:{id_}" if platform in ("twitch", "kick") else f"{platform}:{id_}"
        return LinkRef(platform, kind, id_, key, login.lower() if login else None)

    if host == "twitch.tv":
        if m := re.fullmatch(r"/videos/([0-9]+)/?", path):
            return ref("twitch", "vod", m[1])
        if m := re.fullmatch(r"/([A-Za-z0-9_]+)/clip/([A-Za-z0-9_-]+)/?", path):
            return ref("twitch", "clip", m[2], m[1])
    elif host == "clips.twitch.tv":
        if m := re.fullmatch(r"/([A-Za-z0-9_-]+)/?", path):
            return ref("twitch", "clip", m[1])
    elif host == "kick.com":
        if m := re.fullmatch(rf"/(?:([A-Za-z0-9_-]+)/)?videos?/({_UUID})/?", path):
            return ref("kick", "vod", m[2].lower(), m[1])
        if m := re.fullmatch(r"/([A-Za-z0-9_-]+)/clips/([A-Za-z0-9_]+)/?", path):
            return ref("kick", "clip", m[2], m[1])
        if (m := re.search(r"(?:^|&)clip=([A-Za-z0-9_]+)", q)) and (lm := re.fullmatch(r"/([A-Za-z0-9_-]+)/?", path)):
            return ref("kick", "clip", m[1], lm[1])
    elif host in ("youtube.com", "youtu.be"):
        if host == "youtu.be" and (m := re.fullmatch(r"/([A-Za-z0-9_-]{11})/?", path)):
            return ref("youtube", "video", m[1])
        if m := re.fullmatch(r"/(?:live|shorts)/([A-Za-z0-9_-]{11})/?", path):
            return ref("youtube", "video", m[1])
        if path == "/watch" and (m := re.search(r"(?:^|&)v=([A-Za-z0-9_-]{11})(?:&|$)", q)):
            return ref("youtube", "video", m[1])
    elif host in ("x.com", "twitter.com"):
        if m := re.fullmatch(r"/([A-Za-z0-9_]+)/status/([0-9]+)(?:/video/[0-9])?/?", path):
            return ref("x", "video", m[2])
    return None


def pick_channel(channels: list[Channel], slug: str | None, ref: LinkRef, info: dict) -> Channel | None:
    """zo's pick wins; else match the link/uploader login against the roster (same platform first)."""
    if slug:
        return next((c for c in channels if c.streamer == slug), None)
    names = [n.lower().lstrip("@") for n in (ref.login, info.get("uploader_id"), info.get("channel_id"),
                                              info.get("uploader"), info.get("channel")) if n]
    for same_platform in (True, False):
        for c in channels:
            if same_platform and c.platform != ref.platform:
                continue
            if any(n in (c.login.lower(), c.streamer.lower(), c.name.lower().replace(" ", "")) for n in names):
                return c
    return None


# ---------- detection without chat ----------
def audio_moments(loud: list[tuple[float, float]], channel: str, duration: float, pre_s: float,
                  post_s: float, max_n: int, z_min: float = 2.0, gap_s: float = 45.0,
                  burst_s: float = 5.0, base_s: float = 120.0) -> list[Moment]:
    """Loudness spikes (5 s mean vs the 2 min before it) when the source has no chat replay.
    -> up to max_n moments, strongest first, at least gap_s apart. Times are source offsets."""
    if not loud:
        return []
    pts = sorted(loud)
    step = (pts[-1][0] - pts[0][0]) / max(1, len(pts) - 1) or 0.5
    nb, nbase = max(1, int(burst_s / step)), max(4, int(base_s / step))
    vals = [v for _, v in pts]
    scored = []
    for i in range(nbase + nb, len(pts)):
        burst = mean(vals[i - nb + 1:i + 1])
        base = vals[i - nb - nbase + 1:i - nb + 1]
        z = (burst - mean(base)) / max(pstdev(base), 1.0)
        if z >= z_min:
            scored.append((z, pts[i][0]))
    picked: list[tuple[float, float]] = []
    for z, t in sorted(scored, reverse=True):
        if len(picked) >= max_n:
            break
        if all(abs(t - pt) >= gap_s for _, pt in picked):
            picked.append((z, t))
    out = []
    for z, t in sorted(picked, key=lambda p: p[1]):
        out.append(Moment(channel, t, t, round(z, 2), t, max(0.0, t - pre_s), min(duration, t + post_s),
                          {"z_audio": round(z, 2), "source": "link:audio"}))
    return out


# ---------- downloads ----------
class LinkError(Exception):
    """A failure zo can act on; the message is shown in the dashboard as is."""


def _tail(text: str | None, n: int = 240) -> str:
    lines = [ln for ln in (text or "").strip().splitlines() if ln.strip()]
    return (lines[-1] if lines else "no output")[:n]


class Fetcher:
    """yt-dlp for every platform; TwitchDownloaderCLI for Twitch VOD chat when installed."""

    def __init__(self, ytdlp: str = "yt-dlp", twitch_downloader: str | None = None, run=subprocess.run):
        self.ytdlp, self.tdl, self.run = ytdlp, twitch_downloader, run

    def probe(self, url: str) -> dict:
        r = self.run([self.ytdlp, "-J", "--no-playlist", "--no-warnings", url], capture_output=True, text=True)
        if r.returncode != 0:
            raise LinkError(f"could not open the link: {_tail(r.stderr)}")
        return json.loads(r.stdout)

    def video(self, url: str, out_dir: Path, start: float, end: float | None) -> Path:
        out_dir.mkdir(parents=True, exist_ok=True)
        args = [self.ytdlp, "--no-playlist", "--no-warnings", "--no-part",
                "-f", "bv*[height<=1080]+ba/b[height<=1080]/bv*+ba/b", "--merge-output-format", "mp4",
                "-o", str(out_dir / "source.%(ext)s")]
        if start > 0 or end is not None:
            args += ["--download-sections", f"*{start:.0f}-{end:.0f}" if end is not None else f"*{start:.0f}-inf"]
        r = self.run(args + [url], capture_output=True, text=True)
        if r.returncode != 0:
            raise LinkError(f"download failed: {_tail(r.stderr)}")
        got = sorted(out_dir.glob("source.*"), key=lambda p: p.stat().st_size, reverse=True)
        if not got:
            raise LinkError("download finished but no video file was written")
        return got[0]

    def chat(self, ref: LinkRef, out_dir: Path) -> Path | None:
        if ref.platform != "twitch" or ref.kind != "vod" or not self.tdl:
            return None
        out = out_dir / "chat.json"
        r = self.run([self.tdl, "chatdownload", "--id", ref.id, "-o", str(out), "--collision", "Overwrite"],
                     capture_output=True, text=True)
        if r.returncode != 0 or not out.exists():
            log.warning("chat download failed for %s: %s", ref.key, _tail(r.stderr))
            return None
        return out


def iso(ts: float) -> str:
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).isoformat()


class LinkRunner:
    def __init__(self, settings: Settings, sb, transcriber, judge, fetcher: Fetcher,
                 ffmpeg: str = "ffmpeg", clock=time.time, loudness=None, pipeline_kw: dict | None = None):
        self.s, self.sb, self.tr, self.judge, self.fetch = settings, sb, transcriber, judge, fetcher
        self.ffmpeg, self.clock = ffmpeg, clock
        self._loudness = loudness or (lambda video: vod_loudness(video, ffmpeg))
        self._pipe_kw = pipeline_kw or {}

    # --- Supabase row helpers ---
    def _set(self, row_id: str, **values) -> None:
        self.sb.update("link_jobs", {"id": row_id}, values)

    def _canceled(self, row_id: str) -> bool:
        rows = self.sb.select("link_jobs", id=f"eq.{row_id}", select="status")
        return bool(rows) and rows[0]["status"] == "canceled"

    def run_once(self) -> int:
        """Take the oldest queued link and run it to the end. One link at a time (one GPU)."""
        rows = self.sb.select("link_jobs", status="eq.queued", order="requested_at.asc", limit="1", select="*")
        for row in rows:
            try:
                self.process(row)
            except LinkError as e:
                self._fail(row["id"], str(e))
            except Exception as e:  # noqa: BLE001 - never crash the worker on one bad link
                log.exception("link job %s failed", row["id"])
                self._fail(row["id"], f"{type(e).__name__}: {str(e)[:200]}")
        return len(rows)

    def _fail(self, row_id: str, why: str) -> None:
        if self._canceled(row_id):
            return
        self._set(row_id, status="failed", detail=why[:300], finished_at=iso(self.clock()))

    def process(self, row: dict) -> None:
        rid = row["id"]
        self._set(rid, status="fetching", detail="opening link", started_at=iso(self.clock()))
        ref = parse_link(row["url"])
        if ref is None:
            raise LinkError("unsupported link: paste a Twitch, Kick, YouTube or X video link")
        info = self.fetch.probe(row["url"])
        if info.get("is_live") or info.get("live_status") in ("is_live", "is_upcoming"):
            raise LinkError("this stream is still live: paste the VOD after it ends, or use CLIP THAT")
        ch = pick_channel(self.s.channels, row.get("streamer"), ref, info)
        if ch is None:
            who = info.get("uploader") or info.get("channel") or ref.login or "this channel"
            raise LinkError(f"{who} is not on the roster: pick a streamer and paste again")
        duration = float(info.get("duration") or 0)
        start = float(row.get("start_s") or 0)
        end = float(row["end_s"]) if row.get("end_s") is not None else None
        if duration and start >= duration:
            raise LinkError(f"start {start:.0f} s is past the end of the video ({duration:.0f} s)")
        if duration and end is not None:
            end = min(end, duration)
        span = (end if end is not None else duration) - start
        if span > MAX_SPAN_S:
            raise LinkError("over 8 hours: set a time range and paste again")
        # real clock of the source: stream start (VOD) or upload time, else "ended just now"
        base = float(info.get("release_timestamp") or info.get("timestamp") or (self.clock() - (duration or 0)))
        self._set(rid, source_title=(info.get("title") or "")[:200] or None, duration_s=int(duration) or None,
                  streamer=ch.streamer, detail=f"downloading {_hms(span) if span > 0 else 'video'}")
        work = self.s.work_dir / "links" / rid
        video = self.fetch.video(row["url"], work, start, end)
        if self._canceled(rid):
            return
        chat_file = self.fetch.chat(ref, work)

        self._set(rid, status="detecting", detail="finding moments", chat=chat_file is not None)
        loud = self._loudness(video)
        local_dur = max((t for t, _ in loud), default=span if span > 0 else 0.0)
        msgs: list[tuple[float, str, str]] = []
        if chat_file is not None:   # chat offsets are from VOD start; the file starts at `start`
            hi = start + local_dur
            msgs = [(t - start, u, x) for t, u, x in load_twitchdownloader_chat(chat_file) if start <= t <= hi]
        n = int(row.get("max_clips") or 6)
        short = local_dur <= SHORT_SOURCE_S
        if short:
            moments = [Moment(ch.key, local_dur / 2, local_dur / 2, 0.0, local_dur / 2, 0.0, local_dur,
                              {"source": "link:whole"})]
        elif msgs:
            moments, _ = replay(msgs, ch.detector, ch.reaction_weights, channel=ch.key, loudness=loud)
        else:
            moments = audio_moments(loud, ch.key, local_dur, ch.detector.pre_s, ch.detector.post_s, n * 2)
        found = len(moments)
        t0 = base + start   # epoch of local offset 0
        moments = self._skip_live_dups(ch, [_shift(m, t0) for m in moments], t0, t0 + local_dur)
        top = sorted(moments, key=lambda m: -m.peak_score)[:n]
        self._set(rid, candidates=found)
        if not top:
            self._set(rid, status="done", finished_at=iso(self.clock()),
                      detail="no moments found" if not found else "every moment was already clipped live")
            return
        if self._canceled(rid):
            return

        self._set(rid, status="clipping", detail=f"judging and rendering {len(top)} moment(s)")
        pipe, store = self._pipeline(ch, row, video, t0, work)
        if msgs:
            store.add_messages((ch.key, t0 + t, u, x) for t, u, x in msgs)
        jobs = []
        for m in sorted(top, key=lambda m: m.start_ts):
            jid = pipe.on_moment(m)
            if jid:
                patch = {"badges": ["from_link"], "link_job": rid}
                if short:
                    patch.update(force_keep=True, label="link_pick")
                store.patch_data(jid, patch)
                jobs.append(jid)
        self._set(rid, job_ids=jobs)
        for _ in range(16):
            if self._canceled(rid):
                return
            if not pipe.run_once():
                break
        self._finish(rid, store, jobs)

    def _skip_live_dups(self, ch: Channel, moments: list[Moment], lo: float, hi: float) -> list[Moment]:
        try:
            rows = self.sb.select("clips", channel_key=f"eq.{ch.key}", moment_at=f"gte.{iso(lo - LIVE_DUP_S)}",
                                  select="moment_at")
        except Exception:  # noqa: BLE001 - a failed check must not block the link
            return moments
        made = []
        for r in rows:
            try:
                t = dt.datetime.fromisoformat(str(r["moment_at"]).replace("Z", "+00:00")).timestamp()
            except ValueError:
                continue
            if t <= hi + LIVE_DUP_S:
                made.append(t)
        return [m for m in moments if all(abs(m.start_ts - t) > LIVE_DUP_S for t in made)]

    def _pipeline(self, ch: Channel, row: dict, video: Path, t0: float, work: Path) -> tuple[Pipeline, Store]:
        chans = [replace(c, layout=None) if c.key == ch.key and row.get("full_frame") else c
                 for c in self.s.channels]
        s = replace(self.s, channels=chans)
        store = Store(work / "link.sqlite3")
        cut = vod_extractor(video, self.ffmpeg)

        def extract(buf_dir, start, end, out_dir):  # epoch -> offset in the downloaded file
            cap = cut(buf_dir, start - t0, end - t0, out_dir)
            return {**cap, "start_ts": t0 + cap["start_ts"], "end_ts": t0 + cap["end_ts"]}

        rights = RightsGate(self.sb.active_campaigns, roster={ch.streamer})
        end_clock = lambda: max(self.clock(), t0 + 10 ** 7)  # noqa: E731 - capture never waits on a file
        pipe = Pipeline(s, store, rights, self.tr, self.judge, self.sb, clock=end_clock, extract=extract,
                        **self._pipe_kw)
        return pipe, store

    def _finish(self, rid: str, store: Store, jobs: list[str]) -> None:
        stages = {j: store.job(j) for j in jobs}
        made = sum(1 for j in stages.values() if j.stage == "uploaded")
        held = sum(1 for j in stages.values() if j.stage == "qa_passed")   # dry_run: waits on the PC
        gone = sum(1 for j in stages.values() if j.stage in ("dropped", "qa_failed", "error"))
        judged = cost = 0
        for j in stages.values():
            jd = j.data.get("judgment")
            if jd:
                judged += 1
                usage = jd.get("usage")
                if usage and hasattr(self.judge, "cost_usd"):
                    cost += float(self.judge.cost_usd(usage))
        bits = [f"{made} clip(s) in Review" if made else "no clip passed"]
        if held:
            bits.append(f"{held} held on the PC (dry run)")
        if gone:
            bits.append(f"{gone} dropped")
        left = len(jobs) - made - held - gone
        if left:
            bits.append(f"{left} still working")
        self._set(rid, status="done", clips=made, dropped=gone, judged=judged, cost_usd=round(cost, 4),
                  detail=" · ".join(bits), finished_at=iso(self.clock()))


def _shift(m: Moment, t0: float) -> Moment:
    return Moment(m.channel, m.start_ts + t0, m.peak_ts + t0, m.peak_score, m.last_above_ts + t0,
                  m.window_start + t0, m.window_end + t0, dict(m.features))


def _hms(t: float) -> str:
    t = max(0, int(t))
    return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}"


def build_runner(s: Settings, sb, transcriber, judge) -> LinkRunner:
    fetch = Fetcher(env("YTDLP_BIN", "yt-dlp"), env("TWITCH_DOWNLOADER_BIN") or None)
    return LinkRunner(s, sb, transcriber, judge, fetch, ffmpeg=env("FFMPEG_BIN", "ffmpeg"))
