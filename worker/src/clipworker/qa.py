"""clip-qa: code-only checks before a clip enters review. Zero model tokens.

Pass -> clip may go to `pending_review`. Fail -> list of failed checks.
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .render.captions import H, SAFE_BOTTOM, SIDE_MARGIN, W, parse_ass_events, text_width
from .render.ffmpeg import probe

MAX_BYTES = 50 * 1024 * 1024  # Supabase free plan per-file limit
_LOUD_I = re.compile(r"I:\s*(-?[0-9.]+) LUFS")
_LOUD_TP = re.compile(r"Peak:\s*(-?[0-9.]+) dBFS")
_YAVG = re.compile(r"pts_time:([0-9.]+)\s*\n\s*lavfi\.signalstats\.YAVG=([0-9.]+)")
# Checks adapted from video-director (D093): hook on screen early, phone-readable text, no flashing.
HOOK_S = 3.0          # first caption must appear within this many seconds
MIN_CAPTION_PX = 60   # smallest caption font size readable on a phone at 1080x1920
FLASH_DELTA = 32      # frame-to-frame mean-luma jump (0-255) that counts as a flash edge (~12%)
MAX_FLASHES_PER_S = 3  # WCAG 2.3.1 general flash threshold


@dataclass
class CampaignRules:
    min_s: float = 10.0
    max_s: float = 60.0
    required_tags: list[str] = field(default_factory=list)   # must appear in title/description
    banned_words: list[str] = field(default_factory=list)
    permitted: bool = False                                  # rights gate (D016)
    allow_sfx: bool = True                                   # some campaigns ban added audio
    hook_s: float = HOOK_S


@dataclass
class QAResult:
    failures: list[str]
    metrics: dict

    @property
    def passed(self) -> bool:
        return not self.failures


def measure_loudness(path: Path, ffmpeg: str = "ffmpeg", run=subprocess.run) -> tuple[float, float]:
    r = run([ffmpeg, "-hide_banner", "-nostats", "-i", str(path), "-filter:a",
             "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True, check=True)
    tail = r.stderr[r.stderr.rfind("Summary:"):]
    i = _LOUD_I.search(tail)
    tp = _LOUD_TP.search(tail)
    return (float(i.group(1)) if i else -99.0, float(tp.group(1)) if tp else 0.0)


def luma_series(path: Path, ffmpeg: str = "ffmpeg", run=subprocess.run) -> list[tuple[float, float]]:
    """Mean luma per frame, from a 64 px-wide downscale (fast)."""
    r = run([ffmpeg, "-hide_banner", "-nostats", "-i", str(path), "-an", "-vf",
             "scale=64:-2,signalstats,metadata=mode=print:key=lavfi.signalstats.YAVG:file=-",
             "-f", "null", "-"], capture_output=True, text=True, check=True)
    return [(float(t), float(y)) for t, y in _YAVG.findall(r.stdout)]


def max_flashes_per_s(series: list[tuple[float, float]], delta: float = FLASH_DELTA) -> float:
    """Most flashes (pairs of opposing big luma jumps) in any 1 s window."""
    edges: list[float] = []
    last_sign = 0
    for (_, y0), (t1, y1) in zip(series, series[1:]):
        d = y1 - y0
        if abs(d) >= delta:
            sign = 1 if d > 0 else -1
            if sign != last_sign:
                edges.append(t1)
                last_sign = sign
    best, j = 0, 0
    for i, t in enumerate(edges):
        while edges[j] < t - 1.0:
            j += 1
        best = max(best, i - j + 1)
    return best / 2


def check_clip(video: Path, captions: Path | None, rules: CampaignRules, title: str = "",
               description: str = "", ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe",
               run=subprocess.run) -> QAResult:
    fails: list[str] = []
    m: dict = {}
    if not rules.permitted:
        fails.append("rights: streamer not permitted by an active campaign (D016)")
    info = probe(video, ffprobe, run)
    v = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    dur = float(info["format"].get("duration", 0))
    size = int(info["format"].get("size", Path(video).stat().st_size))
    m.update(duration=dur, size=size)
    if v is None:
        fails.append("video: no video stream")
    else:
        m.update(width=v["width"], height=v["height"], pix_fmt=v.get("pix_fmt"))
        if (v["width"], v["height"]) != (W, H):
            fails.append(f"video: {v['width']}x{v['height']} != {W}x{H}")
        if v.get("pix_fmt") != "yuv420p":
            fails.append(f"video: pix_fmt {v.get('pix_fmt')} != yuv420p")
    if not rules.min_s - 0.25 <= dur <= rules.max_s + 0.25:
        fails.append(f"duration: {dur:.1f}s outside {rules.min_s:.0f}-{rules.max_s:.0f}s")
    if size > MAX_BYTES:
        fails.append(f"size: {size / 1e6:.1f} MB > 50 MB storage limit")
    if v is not None:
        flashes = max_flashes_per_s(luma_series(video, ffmpeg, run))
        m["max_flashes_per_s"] = flashes
        if flashes > MAX_FLASHES_PER_S:
            fails.append(f"video: {flashes:g} flashes/s > {MAX_FLASHES_PER_S} (photosensitivity risk)")
    if a is None:
        fails.append("audio: missing")
    else:
        integ, peak = measure_loudness(video, ffmpeg, run)
        m.update(lufs=integ, true_peak=peak)
        if not -16.5 <= integ <= -11.5:
            fails.append(f"audio: integrated {integ:.1f} LUFS outside -14 +/- 2.5")
        if peak > -0.5:
            fails.append(f"audio: true peak {peak:.1f} dBFS > -0.5 (clipping)")
    if captions is not None:
        text = Path(captions).read_text(encoding="utf-8")
        ev = parse_ass_events(text)
        m["caption_events"] = len(ev)
        if not ev:
            fails.append("captions: no caption events")
        else:
            first = min(st for st, _ in ev)
            m["hook_s"] = round(first, 2)
            if first > rules.hook_s:
                fails.append(f"hook: first caption at {first:.1f}s, needs to be on screen by {rules.hook_s:.0f}s")
        late = [s for s, e in ev if e > dur + 0.3 or s < 0]
        if late:
            fails.append(f"captions: {len(late)} events outside clip (first at {late[0]:.2f}s)")
        mv = re.search(r"^Style: Cap,(?:[^,]*,){20}(\d+),", text, re.M)
        if mv and int(mv.group(1)) < SAFE_BOTTOM:
            fails.append("captions: inside bottom safe area")
        sz = re.search(r"^Style: Cap,[^,]*,(\d+),(?:[^,]*,){13}([\d.]+),", text, re.M)
        if sz:
            size, outline = int(sz.group(1)), float(sz.group(2))
            m["caption_font_px"] = size
            if size < MIN_CAPTION_PX:
                fails.append(f"captions: font {size}px < {MIN_CAPTION_PX}px, too small on a phone")
            pops = [int(x) for x in re.findall(r"\\fscx(\d+)", text)] or [100]
            widest = max((text_width(part, size, outline, max(pops))
                          for line in text.splitlines() if line.startswith("Dialogue:")
                          for part in re.sub(r"\{[^}]*\}", "", line.split(",", 9)[9]).split(r"\N")),
                         default=0)  # \N = forced line break: each line is measured on its own
            m["caption_max_width_px"] = round(widest)
            if widest > W - 2 * SIDE_MARGIN:
                fails.append(f"captions: line ~{widest:.0f}px wide overflows the {W}px frame")
    meta = f"{title}\n{description}".lower()
    for tag in rules.required_tags:
        if tag.lower() not in meta:
            fails.append(f"campaign: required tag {tag!r} missing from title/description")
    for word in rules.banned_words:
        if re.search(rf"\b{re.escape(word.lower())}\b", meta):
            fails.append(f"campaign: banned word {word!r} in title/description")
    return QAResult(fails, m)
