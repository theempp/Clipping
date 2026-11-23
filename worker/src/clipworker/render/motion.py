"""Punch-in zooms and shot-aware reframe (clipper-video plan, P3). Code only, no model.

Zooms: placed at sentence ends from whisperX words (plus the detector peak), at
least `min_gap_s` apart, as ffmpeg zoompan pulses. Gaming layout zooms only the
facecam panel; full-frame (IRL) zooms the whole frame.

Reframe (IRL / no facecam, D115): ffmpeg scene detection splits the clip into shots;
faces are sampled at TRACK_FPS through the whole clip (MediaPipe BlazeFace when installed,
OpenCV Haar as fallback, centre crop with neither). A smoothed camera path follows the face
inside a shot (dead zone, capped pan speed, eased glides) and jumps only on a cut, so the
jump hides inside the cut. The crop is always full height 9:16: it pans, never zooms (D112).
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import urllib.request
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


# --- continuous face tracking (D115) ------------------------------------------------

TRACK_FPS = 4            # face samples per second
DEAD_ZONE = 0.05         # face drift under this (fraction of frame width) keeps the camera still
MAX_PAN_PER_S = 0.22     # camera pan speed cap, fraction of frame width per second
SIMPLIFY_TOL = 0.012     # path keys closer than this to a straight line are dropped
MAX_KEYS = 60            # keeps the ffmpeg expression small

# MediaPipe BlazeFace full range (Apache-2.0, Google). Pinned by hash (light audit 2026-11-23).
FACE_MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/face_detector/"
                  "blaze_face_full_range/float16/1/blaze_face_full_range.tflite")
FACE_MODEL_SHA256 = "3698b18f063835bc609069ef052228fbe86d9c9a6dc8dcb7c7c2d69aed2b181b"
FACE_MODEL_ENV = "CLIPP_FACE_MODEL"
DEFAULT_FACE_MODEL = Path("C:/clip-work/models/blaze_face_full_range.tflite")

_mp_detector = None
_mp_failed = False


def face_model_path() -> Path:
    return Path(os.environ.get(FACE_MODEL_ENV) or DEFAULT_FACE_MODEL)


def ensure_face_model(path: Path | None = None, urlopen=urllib.request.urlopen) -> Path:
    """Download the pinned face model once and check its hash. A mismatch deletes the file and raises."""
    path = Path(path or face_model_path())
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with urlopen(FACE_MODEL_URL, timeout=60) as r:
            path.write_bytes(r.read())
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != FACE_MODEL_SHA256:
        path.unlink(missing_ok=True)
        raise RuntimeError(f"face model hash mismatch ({digest}); file deleted")
    return path


def _mediapipe():
    """The MediaPipe face detector, or None when mediapipe or the model file is missing."""
    global _mp_detector, _mp_failed
    if _mp_detector is not None or _mp_failed:
        return _mp_detector
    model = face_model_path()
    try:
        import mediapipe as mp  # optional dependency: pip install clipworker[reframe]
        from mediapipe.tasks import python as mpt
        from mediapipe.tasks.python import vision
        if not model.exists():
            raise FileNotFoundError(model)
        opts = vision.FaceDetectorOptions(base_options=mpt.BaseOptions(model_asset_path=str(model)),
                                          min_detection_confidence=0.5)
        _mp_detector = (mp, vision.FaceDetector.create_from_options(opts))
    except Exception:  # noqa: BLE001 - any failure falls back to Haar, never breaks a render
        _mp_failed = True
        _mp_detector = None
    return _mp_detector


def detect_face(frame: Path) -> tuple[float, float] | None:
    """(x_centre_fraction, face_area_fraction) of the main face: MediaPipe first, Haar fallback."""
    md = _mediapipe()
    if md is None:
        return face_center_x(frame)
    mp, det = md
    img = mp.Image.create_from_file(str(frame))
    faces = det.detect(img).detections
    if not faces:
        return None
    w, h = img.width, img.height

    def size(d):
        b = d.bounding_box
        return b.width * b.height * d.categories[0].score
    b = max(faces, key=size).bounding_box
    return (b.origin_x + b.width / 2) / w, (b.width * b.height) / (w * h)


def detector_name() -> str:
    return "mediapipe" if _mediapipe() is not None else "haar"


def sample_faces(src: Path, t_in: float, t_out: float, work: Path, ffmpeg: str = "ffmpeg",
                 run=subprocess.run, fps: int = TRACK_FPS) -> list[tuple[float, float | None]]:
    """[(t, x_centre or None)] every 1/fps s through the window. One ffmpeg call for all frames."""
    work.mkdir(parents=True, exist_ok=True)
    for old in work.glob("f_*.jpg"):
        old.unlink()
    run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{t_in:.3f}", "-to", f"{t_out:.3f}",
         "-i", str(src), "-vf", f"fps={fps},scale=640:-2", "-q:v", "4", str(work / "f_%05d.jpg")], check=False)
    out = []
    for i, f in enumerate(sorted(work.glob("f_*.jpg"))):
        hit = detect_face(f)
        out.append((round(i / fps, 3), round(hit[0], 4) if hit else None))
    return out


def _simplify(pts: list[tuple[float, float]], tol: float) -> list[tuple[float, float]]:
    """Ramer-Douglas-Peucker on (t, x): keep the keys that bend the path."""
    if len(pts) < 3:
        return pts
    (t0, x0), (t1, x1) = pts[0], pts[-1]
    worst, idx = 0.0, 0
    for i in range(1, len(pts) - 1):
        t, x = pts[i]
        line = x0 + (x1 - x0) * ((t - t0) / (t1 - t0) if t1 > t0 else 0)
        if abs(x - line) > worst:
            worst, idx = abs(x - line), i
    if worst <= tol:
        return [pts[0], pts[-1]]
    return _simplify(pts[:idx + 1], tol)[:-1] + _simplify(pts[idx:], tol)


def face_path(samples: list[tuple[float, float | None]], cuts: list[float], duration: float,
              fps: int = TRACK_FPS) -> list[tuple[float, float, bool]]:
    """Camera keys [(t, x_centre, jump)] for a 9:16 window. jump=True = hard move at a cut.
    Inside a shot the camera holds while the face stays in the dead zone, then pans toward it
    no faster than MAX_PAN_PER_S. Missing faces hold the last framing (shot start: shot median or 0.5)."""
    keys: list[tuple[float, float, bool]] = []
    dt = 1 / fps
    for n, (a, b) in enumerate(shots(cuts, duration)):
        xs = [(t, x) for t, x in samples if a <= t < b]
        found = sorted(x for _, x in xs if x is not None)
        cam = found[len(found) // 2] if found else 0.5
        # median of 3 kills single-frame misdetections
        raw = [x for _, x in xs]
        filt = []
        for i in range(len(raw)):
            win = sorted(v for v in raw[max(0, i - 1):i + 2] if v is not None)
            filt.append(win[len(win) // 2] if win else None)
        first = next((x for x in filt if x is not None), cam)
        cam = first
        pts = [(a, cam)]
        for (t, _), x in zip(xs, filt):
            if x is not None and abs(x - cam) > DEAD_ZONE:
                target = x - DEAD_ZONE if x > cam else x + DEAD_ZONE
                step = max(-MAX_PAN_PER_S * dt, min(MAX_PAN_PER_S * dt, target - cam))
                cam = cam + step
            pts.append((t, cam))
        pts.append((b, cam))
        pts = _simplify(sorted(dict(pts).items()), SIMPLIFY_TOL)
        keys += [(round(t, 3), round(min(1.0, max(0.0, x)), 4), i == 0 and n > 0) for i, (t, x) in enumerate(pts)]
    tol = SIMPLIFY_TOL
    while len(keys) > MAX_KEYS:  # very long or busy clips: coarsen until the expression stays small
        tol *= 1.5
        out, seg = [], []
        for k in keys + [(None, None, True)]:
            if k[2] and seg:
                pts = _simplify([(t, x) for t, x, _ in seg], tol)
                out += [(t, x, seg[0][2] if i == 0 else False) for i, (t, x) in enumerate(pts)]
                seg = []
            if k[0] is not None:
                seg.append(k)
        keys = out
    return keys


def path_crop_filter(keys: list[tuple[float, float, bool]]) -> str:
    """9:16 full-height crop following the camera keys: eased glide between keys, hard jump on a cut."""
    def x_of(c: str) -> str:
        return f"max(0,min(iw-ow,{c}*iw-ow/2))"
    if not keys:
        return "crop=ih*9/16:ih"
    expr = x_of(f"{keys[-1][1]:.4f}")
    for i in range(len(keys) - 1, 0, -1):
        (t0, x0, _), (t1, x1, jump) = keys[i - 1], keys[i]
        if jump or x0 == x1 or t1 <= t0:
            seg = x_of(f"{x0:.4f}")
        else:
            seg = x_of(f"({x0:.4f}+({x1 - x0:.4f})*{_ramp(f'(t-{t0:.3f})/{t1 - t0:.3f}', 'smooth')})")
        expr = f"if(lt(t,{t1:.3f}),{seg},{expr})"
    return f"crop=ih*9/16:ih:x='{expr}':y=0"


def track(src: Path, t_in: float, t_out: float, work: Path, ffmpeg: str = "ffmpeg", run=subprocess.run,
          cuts: list[float] | None = None) -> tuple[list[tuple[float, float, bool]], list[tuple[float, float, float]]]:
    """(camera keys, per-shot centres for the manifest)."""
    dur = t_out - t_in
    cuts = detect_cuts(src, t_in, t_out, ffmpeg=ffmpeg, run=run) if cuts is None else cuts
    samples = sample_faces(src, t_in, t_out, work, ffmpeg, run)
    keys = face_path(samples, cuts, dur)
    centres = []
    for a, b in shots(cuts, dur):
        xs = sorted(x for t, x in samples if a <= t < b and x is not None)
        centres.append((round(a, 3), round(b, 3), xs[len(xs) // 2] if xs else 0.5))
    return keys, centres
