"""Timed caption over an already-rendered clip (no source footage needed).

Used when Zo adds a caption to a clip whose stream footage is gone, so the clip cannot be
re-rendered: the caption is burned on top of the existing 9:16 render for its first seconds,
then drops off. Text uses the configured caption style (D022: values from references/), at
least 60 px (D114 headline rule), top-centred so it never sits on the word captions.
Nothing else in the clip changes (old renders keep whatever they had, zooms included).
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..config import CaptionStyle
from .captions import H, W, _esc, ass_time

MIN_PX = 60          # D114: headline font >= 60 px
TOP_MARGIN = 260     # clear of the platform top bar on a 1080x1920 frame
MAX_SECONDS = 10.0


@dataclass(frozen=True)
class Overlay:
    text: str
    start_s: float = 0.0
    end_s: float = 2.5


def parse_overlay(p: dict | None) -> Overlay | None:
    """Revision payload {"overlay": {"text", "start_s", "end_s"}} -> Overlay, or None if unusable."""
    o = (p or {}).get("overlay")
    if not isinstance(o, dict):
        return None
    text = " ".join(str(o.get("text") or "").split())[:90]
    if not text:
        return None
    try:
        a = max(0.0, float(o.get("start_s", 0.0)))
        b = min(MAX_SECONDS, float(o.get("end_s", 2.5)))
    except (TypeError, ValueError):
        return None
    if b - a < 0.5:
        return None
    return Overlay(text.upper(), round(a, 2), round(b, 2))


def build_overlay_ass(ov: Overlay, style: CaptionStyle) -> str:
    size = max(MIN_PX, int(style.size))
    return (
        "[Script Info]\nScriptType: v4.00+\n"
        f"PlayResX: {W}\nPlayResY: {H}\nWrapStyle: 0\nScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Head,{style.font},{size},{style.primary_colour},{style.highlight_colour},"
        f"{style.outline_colour},&H00000000,1,0,0,0,100,100,0,0,1,{style.outline},0,8,90,90,"
        f"{TOP_MARGIN},1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        f"Dialogue: 1,{ass_time(ov.start_s)},{ass_time(ov.end_s)},Head,,0,0,0,,{_esc(ov.text)}\n"
    )


def overlay_command(src: Path, out: Path, ass_name: str, ffmpeg: str = "ffmpeg") -> list[str]:
    # ass filter gets a bare filename; the caller runs with cwd = the .ass folder (Windows drive colons).
    return [ffmpeg, "-y", "-v", "error", "-i", str(src), "-vf", f"ass={ass_name}",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
            "-c:a", "copy", "-movflags", "+faststart", str(out)]


def burn_overlay(src: Path, out_dir: Path, ov: Overlay, style: CaptionStyle,
                 ffmpeg: str = "ffmpeg", run=subprocess.run) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "overlay.ass").write_text(build_overlay_ass(ov, style), encoding="utf-8")
    out = out_dir / "clip_overlay.mp4"
    run(overlay_command(Path(src).resolve(), out.resolve(), "overlay.ass", ffmpeg), check=True, cwd=out_dir)
    return out
