"""9:16 render (clip-render skill). ffmpeg only, no model.

Output: 1080x1920 H.264 high yuv420p, fps 30/60 matching source, AAC 48 kHz,
loudnorm -14 LUFS / -1 dBTP, capped bitrate so a 60 s clip stays under the
Supabase 50 MB/file limit (free plan).
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import asdict
from pathlib import Path

from ..config import CaptionStyle, Layout, SfxParams
from ..transcribe import Word
from .captions import H, W, build_ass, shift_words
from .sfx import audio_filter, ensure_whoosh
from .motion import ZoomParams, shot_centres, track_crop_filter, zoom_times, zoompan_filter

CAPTION_VERSION = "ass-v1"


def probe(path: Path, ffprobe: str = "ffprobe", run=subprocess.run) -> dict:
    r = run([ffprobe, "-v", "error", "-print_format", "json", "-show_streams", "-show_format",
             str(path)], check=True, capture_output=True, text=True)
    return json.loads(r.stdout)


def source_fps(info: dict) -> float:
    for s in info.get("streams", []):
        if s.get("codec_type") == "video":
            num, _, den = (s.get("avg_frame_rate") or s.get("r_frame_rate") or "30/1").partition("/")
            try:
                return float(num) / float(den or 1)
            except (ValueError, ZeroDivisionError):
                return 30.0
    return 30.0


def output_fps(src: float) -> int:
    return 60 if src >= 50 else 30


def video_filter(layout: Layout | None, captions_file: str | None, zooms: list[float] | None = None,
                 zoom: ZoomParams | None = None, fps: int = 30,
                 centres: list[tuple[float, float, float]] | None = None,
                 duration: float | None = None, crop_x: float | None = None) -> str:
    moving = bool(zoom) and (bool(zooms) or (zoom.drift > 0 and zoom.on))
    zp = ((lambda w, h: "," + zoompan_filter(zooms or [], zoom, w, h, fps, duration))
          if moving else (lambda w, h: ""))
    if layout is None:  # full frame: face-tracked per shot when centres given, else centre crop
        if centres:
            crop = track_crop_filter(centres)
        elif crop_x is not None:  # editor crop: centre of the 9:16 window, 0..1 of frame width (D098)
            cx = min(1.0, max(0.0, float(crop_x)))
            crop = f"crop=ih*9/16:ih:'max(0,min(iw-ih*9/16,iw*{cx:.4f}-ih*9/32))':0"
        else:
            crop = "crop=ih*9/16:ih"
        g = f"[0:v]{crop},scale={W}:{H},setsar=1{zp(W, H)}[v]"
    else:
        fh = layout.facecam_height
        gh = H - fh
        f, p = layout.facecam, layout.gameplay
        g = (f"[0:v]split=2[a][b];"
             f"[a]crop={f.w}:{f.h}:{f.x}:{f.y},scale={W}:{fh}:force_original_aspect_ratio=increase,"
             f"crop={W}:{fh},setsar=1{zp(W, fh)}[top];"
             f"[b]crop={p.w}:{p.h}:{p.x}:{p.y},scale={W}:{gh}:force_original_aspect_ratio=increase,"
             f"crop={W}:{gh},setsar=1[bot];[top][bot]vstack=inputs=2[v]")
    if captions_file:
        g = g[:-3] + "[v0];[v0]ass=" + captions_file + "[v]"
    return g


def render_command(src: Path, out: Path, t_in: float, t_out: float, layout: Layout | None,
                   captions_file: str | None, fps: int, ffmpeg: str = "ffmpeg",
                   zooms: list[float] | None = None, zoom: ZoomParams | None = None,
                   centres: list[tuple[float, float, float]] | None = None,
                   sfx: SfxParams | None = None, whoosh: Path | None = None,
                   crop_x: float | None = None) -> list[str]:
    a_graph, needs_sfx = audio_filter(zooms or [], sfx if whoosh else None)
    extra_in = ["-i", str(whoosh)] if needs_sfx else []
    return [ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-ss", f"{t_in:.3f}", "-to", f"{t_out:.3f}", "-i", str(src), *extra_in,
            "-filter_complex", video_filter(layout, captions_file, zooms, zoom, fps, centres, t_out - t_in, crop_x)
            + ";" + a_graph,
            "-map", "[v]", "-map", "[a]",
            "-r", str(fps), "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p",
            "-preset", "medium", "-crf", "20", "-maxrate", "6M", "-bufsize", "12M",
            "-c:a", "aac", "-ar", "48000", "-b:a", "160k", "-movflags", "+faststart", str(out)]


MOTION_VERSION = 2  # 2 = eased, rare zooms + gliding reframe (D077)


def source_preview_command(src: Path, out: Path, t_in: float, t_out: float, ffmpeg: str = "ffmpeg") -> list[str]:
    """The original 16:9 window, 640 px tall max, for the dashboard's before/after view."""
    return [ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-ss", f"{t_in:.3f}", "-to", f"{t_out:.3f}", "-i", str(src),
            "-vf", "scale=-2:'min(540,ih)'", "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(out)]


def render_clip(clip_id: str, src: Path, out_dir: Path, t_in: float, t_out: float,
                words: list[Word], layout: Layout | None, style: CaptionStyle | None,
                emphasis: list[str] | None = None, hook_offset: float | None = None,
                manifest_extra: dict | None = None, ffmpeg: str = "ffmpeg",
                ffprobe: str = "ffprobe", run=subprocess.run, zoom: ZoomParams | None = None,
                track: bool = False, sfx: SfxParams | None = None,
                crop_x: float | None = None, cuts: list | None = None) -> dict:
    if style is None:
        raise ValueError("caption_style missing: design values must come from references/ (D022); "
                         "ask Zo before rendering")
    out_dir.mkdir(parents=True, exist_ok=True)
    rel = shift_words(words, t_in, t_out)
    (out_dir / "captions.ass").write_text(build_ass(rel, style, emphasis), encoding="utf-8")
    fps = output_fps(source_fps(probe(src, ffprobe, run)))
    dur = t_out - t_in
    zooms = zoom_times(rel, dur, zoom, hook_offset) if zoom else []
    centres = (shot_centres(Path(src), t_in, t_out, out_dir / "shots", ffmpeg, run)
               if track and layout is None else None)
    whoosh = None
    if sfx is not None and sfx.enabled and zooms:
        whoosh = Path(sfx.file).resolve() if sfx.file else ensure_whoosh(out_dir.parent / "_sfx", ffmpeg, run)
    out = out_dir / "clip.mp4"
    # cwd=out_dir so the ass filter gets a bare filename (no Windows drive-colon escaping).
    run(render_command(Path(src).resolve(), out.resolve(), t_in, t_out, layout, "captions.ass", fps,
                       ffmpeg, zooms, zoom, centres, sfx, whoosh, crop_x), check=True, cwd=str(out_dir))
    # Before/after on the dashboard: the same window of the untouched 16:9 stream, small and light.
    source_prev = out_dir / "source.mp4"
    run(source_preview_command(Path(src).resolve(), source_prev.resolve(), t_in, t_out, ffmpeg),
        check=True, cwd=str(out_dir))
    drop = output_cuts(cuts, t_in, t_out)
    if drop:  # editor splits (D098): Zo dropped segments; cut both copies so before/after stays in step
        for f in (out, source_prev):
            tmp = f.with_name(f.stem + ".cut.mp4")
            run(cut_command(f.resolve(), tmp.resolve(), drop, dur, ffmpeg), check=True, cwd=str(out_dir))
            tmp.replace(f)
        dur -= sum(b - a for a, b in drop)
    thumb_t = min(max(0.0, hook_offset if hook_offset is not None else dur * 0.3), max(0.0, dur - 0.1))
    thumb = out_dir / "thumb.jpg"
    run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{thumb_t:.3f}", "-i", str(out),
         "-frames:v", "1", "-q:v", "3", str(thumb)], check=True)
    manifest = {"clip_id": clip_id, "source": str(src), "window": [t_in, t_out], "fps": fps,
                "layout": asdict(layout) if layout else None, "caption_version": CAPTION_VERSION,
                "zooms": zooms, "shots": centres, "sfx": bool(whoosh), "source_preview": str(source_prev),
                "motion": {"zoom_scale": zoom.scale if zoom else 1.0, "ease": zoom.ease if zoom else None,
                           "moments": zoom.moments if zoom else None, "drift": zoom.drift if zoom else 0.0,
                           "motion_version": MOTION_VERSION},
                "video": str(out), "thumbnail": str(thumb), "duration": round(dur, 3),
                "cuts": [[round(a + t_in, 3), round(b + t_in, 3)] for a, b in drop],
                "peaks": audio_peaks(out, ffmpeg, run),
                **(manifest_extra or {})}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def output_cuts(cuts: list | None, t_in: float, t_out: float) -> list[tuple[float, float]]:
    """Window-relative [a, b] ranges -> merged output-relative ranges inside (0, dur), >= 0.2 s each.
    Never drops everything: at least 1 s must stay."""
    dur = t_out - t_in
    rs = []
    for c in cuts or []:
        try:
            a, b = max(0.0, float(c[0]) - t_in), min(dur, float(c[1]) - t_in)
        except (TypeError, ValueError, IndexError):
            continue
        if b - a >= 0.2:
            rs.append((a, b))
    rs.sort()
    merged: list[tuple[float, float]] = []
    for a, b in rs:
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    if dur - sum(b - a for a, b in merged) < 1.0:
        return []
    return [(round(a, 3), round(b, 3)) for a, b in merged]


def cut_command(src: Path, out: Path, drop: list[tuple[float, float]], dur: float,
                ffmpeg: str = "ffmpeg") -> list[str]:
    """Re-encode `src` keeping everything except the `drop` ranges: trim each kept piece, then concat.
    (trim/concat behaves the same on every ffmpeg build; select/aselect did not.)"""
    keep, t = [], 0.0
    for a, b in drop:
        if a > t:
            keep.append((t, a))
        t = max(t, b)
    if dur > t:
        keep.append((t, dur))
    parts, labels = [], ""
    for i, (a, b) in enumerate(keep):
        parts.append(f"[0:v]trim={a:.3f}:{b:.3f},setpts=PTS-STARTPTS[v{i}]")
        parts.append(f"[0:a]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS[a{i}]")
        labels += f"[v{i}][a{i}]"
    graph = ";".join(parts) + f";{labels}concat=n={len(keep)}:v=1:a=1[v][a]"
    return [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
            "-filter_complex", graph, "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-crf", "20",
            "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-movflags", "+faststart", str(out)]


def audio_peaks(video: Path, ffmpeg: str = "ffmpeg", run=subprocess.run, n: int = 90) -> list[int] | None:
    """Real waveform for the dashboard editor: n buckets of peak level, 0-100. None when it can't be read."""
    import array
    try:
        r = run([ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(video), "-vn", "-ac", "1",
                 "-ar", "4000", "-f", "s16le", "-"], check=True, capture_output=True)
        a = array.array("h")
        a.frombytes(bytes(r.stdout)[: len(r.stdout) // 2 * 2])
    except Exception:  # noqa: BLE001 - the waveform is decoration; never fail a render over it
        return None
    if len(a) < n:
        return None
    step = len(a) // n
    peaks = [max(abs(x) for x in a[i * step:(i + 1) * step]) for i in range(n)]
    top = max(peaks) or 1
    return [max(4, round(100 * p / top)) for p in peaks]
