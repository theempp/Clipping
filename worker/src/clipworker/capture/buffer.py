"""Live buffer: streamlink -> ffmpeg 10 s segments, last 10 min kept.

Segment names carry their wall-clock open time (strftime), which is the same
clock chat uses (worker wall clock; drift logged by Clock). HLS latency means
video runs a few seconds behind chat; the -25 s lead-in absorbs it.
The same ffmpeg process emits ebur128 momentary loudness on stderr.
"""
from __future__ import annotations

import datetime as dt
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

SEGMENT_S = 10
KEEP_S = 600
_SEG_RE = re.compile(r"^(\d{8}-\d{6})\.ts$")
_EBU_RE = re.compile(r"\bt:\s*([0-9.]+)\s+.*?\bM:\s*(-?[0-9.]+|-inf)")


def stream_url(platform: str, login: str) -> str:
    return {"twitch": f"https://twitch.tv/{login}", "kick": f"https://kick.com/{login}"}[platform]


def capture_commands(platform: str, login: str, out_dir: Path,
                     streamlink: str = "streamlink", ffmpeg: str = "ffmpeg") -> tuple[list[str], list[str]]:
    """Two argv lists, to be piped: streamlink stdout -> ffmpeg stdin."""
    sl = [streamlink, "--stdout", "--twitch-disable-ads", "--hls-live-restart=false",
          stream_url(platform, login), "best"]
    if platform != "twitch":
        sl.remove("--twitch-disable-ads")
    ff = [ffmpeg, "-hide_banner", "-loglevel", "info", "-i", "pipe:0",
          "-map", "0", "-c", "copy", "-f", "segment", "-segment_time", str(SEGMENT_S),
          "-reset_timestamps", "1", "-strftime", "1", str(out_dir / "%Y%m%d-%H%M%S.ts"),
          "-map", "0:a:0", "-filter:a", "ebur128=peak=none", "-f", "null", "-"]
    return sl, ff


def parse_ebur128_line(line: str) -> tuple[float, float] | None:
    m = _EBU_RE.search(line)
    if not m:
        return None
    return float(m.group(1)), (-120.0 if m.group(2) == "-inf" else float(m.group(2)))


def parse_ebur128(lines, anchor_ts: float, step_s: float = 1.0) -> list[tuple[float, float]]:
    """ffmpeg ebur128 stderr -> [(ts, momentary LUFS)] downsampled to 1 s (last value wins)."""
    out: dict[int, float] = {}
    for line in lines:
        m = _EBU_RE.search(line)
        if not m:
            continue
        t = float(m.group(1))
        v = -120.0 if m.group(2) == "-inf" else float(m.group(2))
        out[int(t // step_s)] = v
    return [(anchor_ts + k * step_s, v) for k, v in sorted(out.items())]


@dataclass
class Segment:
    path: Path
    start_ts: float
    end_ts: float


def segment_start(path: Path, tz=None) -> float | None:
    m = _SEG_RE.match(path.name)
    if not m:
        return None
    t = dt.datetime.strptime(m.group(1), "%Y%m%d-%H%M%S")
    t = t.replace(tzinfo=tz) if tz else t.astimezone()  # local wall time, like ffmpeg strftime
    return t.timestamp()


def list_segments(buf_dir: Path, tz=None) -> list[Segment]:
    segs = []
    for p in sorted(buf_dir.glob("*.ts")):
        s = segment_start(p, tz)
        if s is not None:
            segs.append(Segment(p, s, s + SEGMENT_S))
    for a, b in zip(segs, segs[1:]):  # real end = next start when known
        a.end_ts = b.start_ts
    return segs


def covering(segs: list[Segment], start: float, end: float) -> list[Segment]:
    return [s for s in segs if s.end_ts > start and s.start_ts < end]


def prune(buf_dir: Path, now: float, keep_s: float = KEEP_S, tz=None) -> int:
    n = 0
    for s in list_segments(buf_dir, tz)[:-1]:  # never delete the segment being written
        if s.end_ts < now - keep_s:
            s.path.unlink(missing_ok=True)
            n += 1
    return n


class WindowMissing(RuntimeError):
    pass


def extract_window(buf_dir: Path, start: float, end: float, out_dir: Path,
                   ffmpeg: str = "ffmpeg", tz=None, run=subprocess.run) -> dict:
    """Concat covering segments, cut [start, end] (stream copy), plus 16 kHz mono wav for ASR."""
    segs = covering(list_segments(buf_dir, tz), start, end)
    if not segs:
        raise WindowMissing(f"no buffer segments cover {start:.0f}-{end:.0f}")
    out_dir.mkdir(parents=True, exist_ok=True)
    lst = out_dir / "concat.txt"
    lst.write_text("".join(f"file '{s.path.as_posix()}'\n" for s in segs), encoding="utf-8")
    offset = max(0.0, start - segs[0].start_ts)
    dur = end - max(start, segs[0].start_ts)
    video = out_dir / "window.mp4"
    audio = out_dir / "window.wav"
    run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
         "-ss", f"{offset:.3f}", "-i", str(lst),
         "-t", f"{dur:.3f}", "-map", "0:v:0", "-map", "0:a:0", "-c:v", "libx264", "-preset", "veryfast", "-crf", "16",
         "-c:a", "aac", "-b:a", "192k", str(video),
         "-t", f"{dur:.3f}", "-map", "0:a:0", "-ac", "1", "-ar", "16000", str(audio)], check=True)
    covered_start = max(start, segs[0].start_ts)
    return {"video": str(video), "audio": str(audio), "start_ts": covered_start,
            "end_ts": covered_start + dur, "partial": segs[0].start_ts > start or segs[-1].end_ts < end}
