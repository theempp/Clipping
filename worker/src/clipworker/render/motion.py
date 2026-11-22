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


def _emphatic(text: str) -> bool:
    """A shouted line: ends in '!' or is a real word in capitals (WHAT, NO)."""
    t = text.strip().strip("\"'")
    core = re.sub(r"[^A-Za-z]", "", t)
    return t.endswith("!") or (len(core) >= 3 and core.isupper())


def zoom_times(words: list[Word], duration: float, p: ZoomParams,
               peak: float | None = None) -> list[float]:
    """Start times (clip seconds) for zoom pulses. Pure function.

    moments: "peak" = detector peak only; "emphasis" = peak, then shouted lines;
    "sentences" = peak, then every sentence end or pause (the old D051 behaviour)."""
    if not p.on:
        return []
    span = 2 * p.ramp_s + p.hold_s
    cands: list[float] = []
    if peak is not None and 0 <= peak < duration:
        cands.append(peak)
    for i, w in enumerate(words):
        if p.moments == "peak":
            break
        if p.moments == "emphasis":
            if _emphatic(w.text):  # land the push on the shout itself
                cands.append(max(0.0, w.start - p.ramp_s * 0.5) + p.lead_s)
            continue
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


def _ramp(x: str, ease: str) -> str:
    """0 -> 1 ramp over x in [0, 1]. smooth = cosine ease-in-out: no hard start or stop."""
    c = f"clip({x},0,1)"
    return c if ease == "linear" else f"(1-cos(PI*{c}))/2"


def zoom_expr(times: list[float], p: ZoomParams, duration: float | None = None) -> str:
    """zoompan `z` expression: 1 + slow drift + (scale-1) * sum of eased pulses over input time."""
    drift = f"+{p.drift:.4f}*clip(it/{duration:.3f},0,1)" if p.drift > 0 and duration else ""
    if not times:
        return f"1{drift}" if drift else "1"
    a = p.scale - 1
    pulses = []
    for t in times:
        end = t + 2 * p.ramp_s + p.hold_s
        pulses.append(f"{_ramp(f'(it-{t:.3f})/{p.ramp_s:.3f}', p.ease)}"
                      f"*{_ramp(f'({end:.3f}-it)/{p.ramp_s:.3f}', p.ease)}")
    return f"1{drift}+{a:.4f}*({'+'.join(pulses)})"


def zoompan_filter(times: list[float], p: ZoomParams, w: int, h: int, fps: int,
                   duration: float | None = None) -> str:
    """Zoom on a 2x upscaled panel: zoompan snaps its window to whole pixels, which at 1x
    shows as a stepped, shaky push. At 2x the steps are half a pixel and read as smooth."""
    z = zoom_expr(times, p, duration)
    return (f"scale=iw*2:ih*2:flags=bicubic,"
            f"zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
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


GLIDE_S = 0.6          # camera glide time between nearby framings
GLIDE_MAX_SHIFT = 0.2  # bigger moves than this (fraction of width) stay hard cuts


def track_crop_filter(centres: list[tuple[float, float, float]]) -> str:
    """9:16 full-height crop that follows each shot's face.

    A big move (a real cut to a different framing) jumps inside the cut. A small move
    (same scene, the face drifted, or a false cut) glides there with an eased pan instead
    of snapping (D077: no robotic camera)."""
    def x_of(c: str) -> str:
        return f"max(0,min(iw-ow,{c}*iw-ow/2))"
    if not centres:
        return "crop=ih*9/16:ih"
    # Built from the last shot backwards: `expr` is always the x for t >= the current shot's start.
    expr = x_of(f"{centres[-1][2]:.4f}")
    for i in range(len(centres) - 1, 0, -1):
        a, c, prev = centres[i][0], centres[i][2], centres[i - 1][2]
        if abs(c - prev) <= GLIDE_MAX_SHIFT and c != prev:
            pos = f"({prev:.4f}+({c - prev:.4f})*{_ramp(f'(t-{a:.3f})/{GLIDE_S:.3f}', 'smooth')})"
            expr = f"if(lt(t,{a + GLIDE_S:.3f}),{x_of(pos)},{expr})"
        expr = f"if(lt(t,{a:.3f}),{x_of(f'{prev:.4f}')},{expr})"
    return f"crop=ih*9/16:ih:x='{expr}':y=0"
