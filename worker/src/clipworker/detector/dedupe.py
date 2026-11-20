"""Dedupe (Install plan gap 6): one moment, one clip.

Level 1 (detection): channel + 10 s bucket of the trigger -> unique job key.
Level 2 (after transcription): squad streams (Lacy/Clix share lobbies) can
yield the same moment on two channels. Same moment = triggers within 30 s and
transcript word-shingle Jaccard >= 0.5.
"""
from __future__ import annotations

import hashlib
import re


def detection_key(channel: str, trigger_ts: float, bucket_s: float = 10.0) -> str:
    return f"{channel}:{int(trigger_ts // bucket_s)}"


def _shingles(text: str, n: int = 3) -> set[tuple[str, ...]]:
    words = re.findall(r"[a-z0-9']+", text.lower())
    if len(words) < n:
        return {tuple(words)} if words else set()
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}


def jaccard(a: str, b: str) -> float:
    sa, sb = _shingles(a), _shingles(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def same_moment(ts_a: float, text_a: str, ts_b: float, text_b: str,
                max_dt: float = 30.0, min_sim: float = 0.5) -> bool:
    return abs(ts_a - ts_b) <= max_dt and jaccard(text_a, text_b) >= min_sim


def content_hash(*parts: str | bytes) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p if isinstance(p, bytes) else p.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()
