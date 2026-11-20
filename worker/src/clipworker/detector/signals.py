"""Pure feature math. No I/O, no model."""
from __future__ import annotations

import re
from statistics import median

_WORD = re.compile(r"[A-Z0-9?!']+")


def robust_z(x: float, history: list[float], floor_scale: float) -> float:
    """(x - median) / max(1.4826*MAD, floor). Robust to one-off spam spikes."""
    if not history:
        return 0.0
    med = median(history)
    mad = median(abs(h - med) for h in history)
    return (x - med) / max(1.4826 * mad, floor_scale)


def compile_reactions(weights: dict[str, float]):
    """Split into whole-word tokens and multi-word / symbol phrases."""
    words, phrases = {}, {}
    for tok, w in weights.items():
        t = tok.upper().strip()
        if " " in t or not re.fullmatch(r"[A-Z0-9']+", t):
            phrases[t] = w
        else:
            words[t] = w
    return words, phrases


def reaction_weight(text: str, compiled) -> float:
    """Max weight of any reaction token in one message (one message = one vote)."""
    words, phrases = compiled
    up = " ".join(text.upper().split())
    best = 0.0
    for tok in _WORD.findall(up):
        w = words.get(tok)
        if w and w > best:
            best = w
    for p, w in phrases.items():
        if w > best and p in up:
            best = w
    return best
