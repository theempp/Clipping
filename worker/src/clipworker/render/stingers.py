"""GTA stingers (D115): pre-baked transparent overlays from echris6/gta-components, GTA 6 clips only.

The components are HTML (HyperFrames + GSAP). They are baked ONCE, offline, in Windows Sandbox
(ops/stingers/bake.ps1), with bg=none, to ProRes 4444 .mov files. The worker never runs HyperFrames,
Node or a browser: it only overlays the baked file with ffmpeg (tools.stinger_command).

Only these 5 are allowed (repo-audit, Tools and Repos 2026-11-23). The repo's zoom components
(Punch-in zoom, Magnifier zoom, Punch zoom transition) are never baked (D112).
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path

VERSION = "v1"  # bump when a sting is re-baked, so old files are not reused


@dataclass(frozen=True)
class Sting:
    name: str
    component: str      # path inside gta-components at the audited commit
    variant: str
    length_s: float     # the comp's own duration
    mono: bool          # drain the clip under it to black-and-white
    categories: frozenset[str]  # judge categories it fits


STINGS: dict[str, Sting] = {s.name: s for s in (
    Sting("wasted", "shorts/09-wasted-stamp", "0", 5.0, True, frozenset({"fail"})),
    Sting("busted", "shorts/09-wasted-stamp", "1", 5.0, True, frozenset({"fail", "rage"})),
    Sting("mission_passed", "shorts/10-mission-passed", "0", 5.4, False, frozenset({"clutch"})),
    Sting("mission_failed", "shorts/10-mission-passed", "1", 5.4, True, frozenset({"fail", "funny"})),
    Sting("wanted_level", "shorts/08-wanted-level", "0", 6.1, False, frozenset({"rage", "clutch"})),
)}


def fits(category: str | None) -> list[Sting]:
    return [s for s in STINGS.values() if category in s.categories]


def asset_path(stinger_dir: Path | str, s: Sting) -> Path:
    return Path(stinger_dir) / f"{s.name}-{VERSION}.mov"


def choose(category: str | None, rng: random.Random, stinger_dir: Path | str | None) -> Sting | None:
    """A sting that fits the moment and is baked on disk. None = skip the tool (never fatal)."""
    if not stinger_dir:
        return None
    ok = [s for s in fits(category) if asset_path(stinger_dir, s).exists()]
    return rng.choice(ok) if ok else None


def placement(peak_rel: float, clip_dur: float, length_s: float) -> tuple[float, float]:
    """(at, length): land on the peak, cut short so it ends with the clip (the sting's blur-out may
    be lost on a short tail; the hook and payoff are what matter). Starts no earlier than 0."""
    at = min(max(0.0, peak_rel), max(0.0, clip_dur - 1.0))
    return round(at, 3), round(max(0.5, min(length_s, clip_dur - at)), 3)
