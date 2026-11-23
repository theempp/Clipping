"""Synthesized SFX library (D114). ffmpeg lavfi only: no third-party audio, no licence question.

hit      low thump with a short noise click
glitch   bit-crushed, stuttering noise burst
whoosh   filtered pink noise sweep (see sfx.py)
rewind   tape rewind: rising chirp over hiss, for the flashback (D113)
Files are cached by name and version, so a tuned recipe bumps the version.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from .sfx import ensure_whoosh

VERSION = "v1"
_GRAPHS = {
    "hit": ("aevalsrc='0.95*sin(2*PI*58*t*exp(-7*t))*exp(-5.5*t)+0.25*random(0)*exp(-60*t)':d=0.7:s=48000",
            "alimiter=limit=0.95"),
    "glitch": ("anoisesrc=d=0.4:c=white:a=0.7:seed=11",
               "highpass=f=300,acrusher=bits=4:mode=log:aa=0,tremolo=f=28:d=1,afade=t=out:st=0.28:d=0.12"),
    "rewind": ("aevalsrc='0.35*sin(2*PI*(240*t+2600*t*t))+0.12*random(1)':d=1.3:s=48000",
               "highpass=f=180,lowpass=f=7000,vibrato=f=14:d=0.35,afade=t=in:d=0.08,afade=t=out:st=1.05:d=0.25"),
}


def ensure_sfx(name: str, cache_dir: Path, ffmpeg: str = "ffmpeg", run=subprocess.run) -> Path:
    if name == "whoosh":
        return ensure_whoosh(cache_dir, ffmpeg, run)
    src, af = _GRAPHS[name]
    out = Path(cache_dir) / f"{name}-{VERSION}.wav"
    if out.exists():
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", src, "-af", af,
         "-ar", "48000", "-ac", "2", str(out)], check=True)
    return out


TOOL_TO_SFX = {"sfx_hit": "hit", "sfx_glitch": "glitch", "sfx_whoosh": "whoosh"}
