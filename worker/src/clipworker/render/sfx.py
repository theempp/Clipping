"""Whoosh sound effects on zooms (clipper-video plan, P4). ffmpeg only.

The default whoosh is synthesized (filtered pink noise with a fade in/out), so
there is no third-party audio and no licence question.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from ..config import SfxParams

WHOOSH_S = 0.6


def ensure_whoosh(cache_dir: Path, ffmpeg: str = "ffmpeg", run=subprocess.run) -> Path:
    out = Path(cache_dir) / "whoosh-v1.wav"
    if out.exists():
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
         "-i", f"anoisesrc=d={WHOOSH_S}:c=pink:a=0.8:seed=7",
         "-af", ("highpass=f=250,lowpass=f=6000,"
                 f"afade=t=in:d=0.3:curve=exp,afade=t=out:st=0.3:d=0.3:curve=exp"),
         "-ar", "48000", "-ac", "2", str(out)], check=True)
    return out


def audio_filter(times: list[float], p: SfxParams | None) -> tuple[str, bool]:
    """filter_complex audio chain -> [a]. Returns (graph, uses_input_1)."""
    norm = "loudnorm=I=-14:TP=-1.5:LRA=11"
    if not times or p is None or not p.enabled:
        return f"[0:a:0]{norm}[a]", False
    n = len(times)
    parts = [f"[1:a]volume={p.volume_db}dB,asplit={n}" + "".join(f"[w{i}]" for i in range(n))
             if n > 1 else f"[1:a]volume={p.volume_db}dB[w0]"]
    for i, t in enumerate(times):
        ms = max(0, int(round((t - p.lead_s) * 1000)))
        parts.append(f"[w{i}]adelay={ms}|{ms}[d{i}]")
    mix_in = "[0:a:0]" + "".join(f"[d{i}]" for i in range(n))
    parts.append(f"{mix_in}amix=inputs={n + 1}:duration=first:normalize=0,{norm}[a]")
    return ";".join(parts), True
