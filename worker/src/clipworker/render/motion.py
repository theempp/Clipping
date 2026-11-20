"""Punch-in zooms and shot-aware reframe (clipper-video plan, P3). Code only, no model.

Zooms: placed at sentence ends from whisperX words (plus the detector peak), at
least `min_gap_s` apart, as ffmpeg zoompan pulses. Gaming layout zooms only the
facecam panel; full-frame (IRL) zooms the whole frame.

Reframe (IRL / no facecam): ffmpeg scene detection splits the clip into shots;
OpenCV finds the largest face in each shot and the 9:16 crop is centred on it,
changing only on a cut so the jump hides inside the cut. OpenCV is optional:
without it every shot is centre-cropped.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from ..config import ZoomParams
from ..transcribe import Word

_SENT_END = (".", "!", "?")
SENTENCE_PAUSE_S = 0.5


def zoom_times(words: list[Word], duration: float, p: ZoomParams,
               peak: float | None = None) -> list[float]:
    """Start times (clip seconds) for zoom pulses. Pure function."""
    if not p.on:
        return []
    span = 2 * p.ramp_s + p.hold_s
    cands: list[float] = []
    if peak is not None and 0 <= peak < duration:
        cands.append(peak)
    for i, w in enumerate(words):
        nxt = words[i + 1].start if i + 1 < len(words) else None
        ends = w.text.rstrip().endswith(_SENT_END)
        pause = nxt is not None and nxt - w.end >= SENTENCE_PAUSE_S
        if ends or pause:
            cands.append(w.end + p.lead_s)
    out: list[float] = []
    for t in cands:  # peak first, then sentence ends in time order
        if t < 0.5 or t + span > duration:
            continue
        if all(abs(t - o) >= max(p.min_gap_s, span) for o in out):
            out.append(t)
        if len(out) >= p.max_zooms:
            break
    return sorted(round(t, 3) for t in out)


def zoom_expr(times: list[float], p: ZoomParams) -> str:
    """zoompan `z` expression: 1 + (scale-1) * sum of trapezoid pulses over input time."""
    if not times:
        return "1"
    a = p.scale - 1
    pulses = []
    for t in times:
        up, down = t + p.ramp_s, t + p.ramp_s + p.hold_s
        pulses.append(f"clip((it-{t:.3f})/{p.ramp_s:.3f},0,1)*clip(({down + p.ramp_s:.3f}-it)/{p.ramp_s:.3f},0,1)")
    return f"1+{a:.4f}*({'+'.join(pulses)})"


def zoompan_filter(times: list[float], p: ZoomParams, w: int, h: int, fps: int) -> str:
    z = zoom_expr(times, p)
    return (f"zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d=1:s={w}x{h}:fps={fps}")


# --- shot detection + face centring -------------------------------------------------

def detect_cuts(src: Path, t_in: float, t_out: float, threshold: float = 0.3,
                ffmpeg: str = "ffmpeg", run=subprocess.run) -> list[float]:
    """Scene-cut times in clip seconds (0 = t_in)."""
    r = run([ffmpeg, "-hide_banner", "-ss", f"{t_in:.3f}", "-to", f"{t_out:.3f}", "-i", str(src),
             "-vf", f"scale=320:-2,select='gt(scene,{threshold})',showinfo", "-an", "-f", "null", "-"],
            capture_output=True, text=True)
    cuts = [float(m) for m in re.findall(r"pts_time:([\d.]+)", r.stderr or "")]
    return sorted(c for c in cuts if 0.3 < c < (t_out - t_in) - 0.3)


def shots(cuts: list[float], duration: float) -> list[tuple[float, float]]:
    edges = [0.0, *cuts, duration]
    return [(a, b) for a, b in zip(edges, edges[1:]) if b - a > 0.05]


def face_center_x(frame_png: Path) -> tuple[float, float] | None:
    """(x_centre_fraction, face_area_fraction) of the largest face, or None."""
    try:
        import cv2  # optional dependency: pip install clipworker[reframe]
    except ImportError:
        return None
    img = cv2.imread(str(frame_png))
    if img is None:
        return None
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    casc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    h, w = gray.shape
    faces = casc.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=6,
                                  minSize=(max(24, w // 30), max(24, w // 30)))
    if len(faces) == 0:
        return None
    x, y, fw, fh = max(faces, key=lambda f: f[2] * f[3])
    return (x + fw / 2) / w, (fw * fh) / (w * h)


def shot_centres(src: Path, t_in: float, t_out: float, work: Path, ffmpeg: str = "ffmpeg",
                 run=subprocess.run, cuts: list[float] | None = None
                 ) -> list[tuple[float, float, float]]:
    """[(start, end, x_centre_fraction)] per shot. Centre 0.5 when no face is found."""
    dur = t_out - t_in
    cuts = detect_cuts(src, t_in, t_out, ffmpeg=ffmpeg, run=run) if cuts is None else cuts
    out = []
    work.mkdir(parents=True, exist_ok=True)
    for i, (a, b) in enumerate(shots(cuts, dur)):
        xs = []
        for k, frac in enumerate((0.25, 0.5, 0.75)):  # 3 samples per shot, median
            png = work / f"shot{i}_{k}.png"
            run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{t_in + a + (b - a) * frac:.3f}",
                 "-i", str(src), "-frames:v", "1", str(png)], check=False)
            f = face_center_x(png) if png.exists() else None
            if f:
                xs.append(f[0])
        xs.sort()
        out.append((round(a, 3), round(b, 3), round(xs[len(xs) // 2], 4) if xs else 0.5))
    return out


def track_crop_filter(centres: list[tuple[float, float, float]]) -> str:
    """9:16 full-height crop whose x jumps to each shot's face (only at cuts)."""
    def x_of(c: float) -> str:
        return f"max(0,min(iw-ow,{c:.4f}*iw-ow/2))"
    if not centres:
        return "crop=ih*9/16:ih"
    expr = x_of(centres[-1][2])
    for a, b, c in reversed(centres[:-1]):
        expr = f"if(lt(t,{b:.3f}),{x_of(c)},{expr})"
    return f"crop=ih*9/16:ih:x='{expr}':y=0"
