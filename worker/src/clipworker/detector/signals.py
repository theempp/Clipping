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


MOODS = {  # chat mood shares (D089): which share of the burst laughs, hypes or is shocked
    "laugh": {"KEKW", "LUL", "OMEGALUL", "LMAO", "LOL", "LMFAO", "ICANT", "😂", "💀"},
    "hype": {"POG", "POGGERS", "POGCHAMP", "W", "LETSGO", "GOAT", "🔥"},
    "shock": {"??", "???", "WHAT", "NOWAY", "WTF", "BRO", "😳", "😱"},
}


def message_tokens(text: str) -> set[str]:
    up = " ".join(text.upper().split())
    raw = _WORD.findall(up)
    toks = set(raw) | {t.strip("?!'") for t in raw if t.strip("?!'")} | {c for c in up if ord(c) > 0x2000}
    if any(t.startswith("??") or t.endswith("??") for t in raw):
        toks.add("??")
    if "NO WAY" in up:
        toks.add("NOWAY")
    if "LETS GO" in up or "LET'S GO" in up:
        toks.add("LETSGO")
    return toks


def mood_hits(text: str) -> int:
    """Number of mood families (laugh/hype/shock) a message hits (0-3)."""
    toks = message_tokens(text)
    return sum(1 for words in MOODS.values() if toks & words)


def lift_weight(text: str, lift: dict[str, float]) -> float:
    """Max learned chat-word lift in one message (brain.json chat_word_lift)."""
    if not lift:
        return 0.0
    return max((lift.get(t, 0.0) for t in message_tokens(text)), default=0.0)


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
