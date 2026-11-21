"""Roster rules (D069): which live channels to capture, and the GTA 6 score boost.

core       every stream is clipped; while the game is GTA 6 the detector score is
           multiplied by the channel's gta6_boost (more and higher-ranked moments).
gta6_only  captured only while the stream's category is GTA 6.

At most `max_channels` are captured at once (CPU/GPU limit). When more are
eligible: GTA 6 streams first, then core before gta6_only, then most viewers.
"""
from __future__ import annotations

from dataclasses import dataclass

from .config import Channel, Gta6Match


@dataclass(frozen=True)
class Pick:
    capture: set[str]          # channel keys to capture now
    skipped: list[str]         # eligible but over the concurrency cap
    boost: dict[str, float]    # channel key -> detector multiplier (1.0 = none)
    on_gta6: set[str]          # live keys whose category is GTA 6


def pick_captures(channels: list[Channel], info: dict[str, dict], permitted: set[str],
                  max_n: int, gta6: Gta6Match) -> Pick:
    on_gta6 = {k for k, v in info.items() if gta6.matches(v.get("game_id"), v.get("game"))}
    eligible = []
    for c in channels:
        if c.key not in info or c.key not in permitted:
            continue
        if c.group == "gta6_only" and c.key not in on_gta6:
            continue
        eligible.append(c)
    eligible.sort(key=lambda c: (c.key not in on_gta6, c.group != "core",
                                 -(info[c.key].get("viewers") or 0), c.key))
    chosen = eligible[:max_n]
    boost = {c.key: (c.gta6_boost if c.key in on_gta6 else 1.0) for c in channels}
    return Pick({c.key for c in chosen}, [c.key for c in eligible[max_n:]], boost, on_gta6)
