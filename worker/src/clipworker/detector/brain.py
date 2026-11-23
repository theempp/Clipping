"""Streamer Brain (D089/D099): Zo's per-streamer sliders and chat words from the dashboard.

Sliders are 0-100 with dashboard defaults. Each one scales a detector weight by value / default,
so an untouched brain leaves the channel's tuned config exactly as it is.
  chat_spike -> w_chat and w_unique (how much a chat burst counts)
  voice_peak -> w_audio
  chat_words -> w_reaction, and `words` join the reaction list at REACTION_W
viewer_clips and approved_match have no detector signal yet: saved only.
"""
from __future__ import annotations

from dataclasses import replace

from ..config import DetectorParams

DEFAULTS = {"chat_spike": 70, "voice_peak": 55, "chat_words": 75, "viewer_clips": 35, "approved_match": 60}
APPLIED = ("chat_spike", "voice_peak", "chat_words")
REACTION_W = 1.0
MAX_FACTOR = 2.0


def _factor(weights: dict, key: str) -> float:
    try:
        v = float(weights.get(key, DEFAULTS[key]))
    except (TypeError, ValueError):
        return 1.0
    return max(0.0, min(MAX_FACTOR, v / DEFAULTS[key]))


def apply_brain(params: DetectorParams, reactions: dict[str, float],
                weights: dict | None, words: list | None) -> tuple[DetectorParams, dict[str, float]]:
    """(params, reaction weights) for one channel. Never mutates the inputs."""
    w = weights or {}
    chat, voice, react = _factor(w, "chat_spike"), _factor(w, "voice_peak"), _factor(w, "chat_words")
    p = replace(params, w_chat=params.w_chat * chat, w_unique=params.w_unique * chat,
                w_audio=params.w_audio * voice, w_reaction=params.w_reaction * react)
    r = dict(reactions)
    for word in words or []:
        t = str(word).strip().upper()[:40]
        if t:
            r[t] = max(r.get(t, 0.0), REACTION_W)
    return p, r
