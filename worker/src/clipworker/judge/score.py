"""0-100 clip score (D089; zo-clipper reference/moment-scoring.md).

50 measured (code, free) + 50 judged (model, shortlist only), plus viewers_clipped +5
and dead air > 30% -15. score_10 = round(score / 10) keeps the queue sort working.
Our own weights for streams; the 50/50 split is the only idea taken from Clipper.
"""
from __future__ import annotations

from bisect import bisect_left

JUDGED_PARTS = ("hook", "payoff", "standalone", "emotion", "share")
DROP_BELOW = 60
HOOK_FULL_S, HOOK_ZERO_S = 1.5, 8.0
LEN_FULL, LEN_ZERO = (12.0, 20.0), (8.0, 60.0)


def _lin(x: float, zero: float, full: float) -> float:
    """0 at `zero`, 1 at `full`, linear between, clamped."""
    if full == zero:
        return 1.0 if x >= full else 0.0
    return max(0.0, min(1.0, (x - zero) / (full - zero)))


def peak_part(score: float, history: list[float], threshold: float) -> float:
    """15 pts: percentile vs this stream's own earlier candidates; <5 history = vs threshold."""
    if len(history) >= 5:
        h = sorted(history)
        return 15.0 * bisect_left(h, score) / len(h)
    return 15.0 * _lin(score, threshold, 2 * threshold)


def hook_part(signal_s: float | None) -> float:
    """15 pts: seconds from clip start to the first strong signal."""
    if signal_s is None:
        return 0.0
    return 15.0 * _lin(-max(0.0, signal_s), -HOOK_ZERO_S, -HOOK_FULL_S)


def length_part(length: float, min_s: float = 0.0, max_s: float = 1e9) -> float:
    """10 pts: full at 12-20 s, 0 at 8 s / 60 s; outside the campaign range = 0."""
    if length < min_s or length > max_s:
        return 0.0
    lo_full, hi_full = max(LEN_FULL[0], min_s), min(LEN_FULL[1], max_s)
    lo_zero, hi_zero = min(LEN_ZERO[0], lo_full), max(LEN_ZERO[1], hi_full)
    if length < lo_full:
        return 10.0 * _lin(length, lo_zero, lo_full)
    if length > hi_full:
        return 10.0 * _lin(-length, -hi_zero, -hi_full)
    return 10.0


def density_part(words_per_s: float, hype_words: int, events: int) -> float:
    """10 pts: talk rate (3 w/s = full), hype words (3 = full), laugh/shout events (2 = full)."""
    return 10.0 * (0.5 * min(1.0, words_per_s / 3.0) + 0.3 * min(1.0, hype_words / 3.0)
                   + 0.2 * min(1.0, events / 2.0))


def measured(*, detector_score: float, history: list[float], threshold: float,
             trim_in: float, trim_out: float, words, peak_rel: float | None,
             hype_tokens: set[str], min_s: float = 0.0, max_s: float = 1e9,
             shout: bool = False) -> dict:
    """Measured parts from code only. Times are seconds from window start."""
    inside = [w for w in words if trim_in <= w.start < trim_out]
    hype = [w for w in inside if w.text.upper().strip(".,!?'\"") in hype_tokens]
    signals = [w.start for w in hype]
    if peak_rel is not None and peak_rel >= trim_in:
        signals.append(peak_rel)
    if inside:
        signals.append(inside[0].start)  # speech from the first second is a hook in itself
    length = max(0.0, trim_out - trim_in)
    first = min(signals) - trim_in if signals else None
    return {
        "peak": round(peak_part(detector_score, history, threshold), 1),
        "hook_speed": round(hook_part(first), 1),
        "length": round(length_part(length, min_s, max_s), 1),
        "density": round(density_part(len(inside) / length if length else 0.0, len(hype),
                                      int(shout)), 1),
    }


def judged(parts: dict | None) -> dict | None:
    if not parts:
        return None
    out = {}
    for k in JUDGED_PARTS:
        try:
            out[k] = max(0, min(10, int(round(float(parts.get(k, 0))))))
        except (TypeError, ValueError):
            out[k] = 0
    return out


def total(meas: dict, judg: dict | None, viewers_clipped: bool = False,
          dead_air_ratio: float = 0.0) -> tuple[int, dict]:
    bonus = {"viewers_clipped": 5 if viewers_clipped else 0,
             "dead_air": -15 if dead_air_ratio > 0.3 else 0}
    s = sum(meas.values()) + sum((judg or {}).values()) + sum(bonus.values())
    return max(0, min(100, int(round(s)))), bonus


def score_10(score: int) -> int:
    return max(1, min(10, int(score / 10 + 0.5)))  # half up (65 -> 7), not banker's rounding
