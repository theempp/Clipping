"""Stand-in judge when no Grok key is set (D071). Pure code, no model, no spend.

Keeps every detected moment and cuts a window around the chat peak, so the
pipeline still renders clips into the review queue. Titles say "UNJUDGED" so
Zo knows the model never saw them; nothing auto-publishes (approval gate).
"""
from __future__ import annotations

from ..transcribe import Word
from .grok import Judgment, snap_to_words

PRE_PEAK_S = 18.0   # lead-in before the chat peak (the moment usually happens just before chat reacts)


class HeuristicJudge:
    wants_peak = True

    def cost_usd(self, usage: dict) -> float:
        return 0.0

    def judge(self, words: list[Word], chat_sample: list[str], scores: dict, rules_summary: str,
              duration: float, min_len: float, max_len: float, peak_rel: float | None = None) -> Judgment:
        peak = duration * 0.6 if peak_rel is None else peak_rel
        length = max(min_len, min(max_len, 40.0, duration))
        t_in = max(0.0, min(peak - PRE_PEAK_S, duration - length))
        t_out = min(duration, t_in + length)
        t_in, t_out = snap_to_words(t_in, t_out, words, verbal=False)
        t_out = min(t_out, t_in + max_len, duration)
        said = " ".join(w.text for w in words if t_in <= w.start < t_out).strip()
        hook = (said[:60].rsplit(" ", 1)[0] + "...") if len(said) > 60 else (said or "Chat spike")
        score = float(scores.get("score", 0))
        return Judgment(keep=True, category="other", trim_in=round(t_in, 2), trim_out=round(t_out, 2),
                        hook=hook, title=f"UNJUDGED: {hook}"[:100], emphasis_words=[],
                        confidence=round(min(0.99, score / 6), 2), reason=f"no judge; detector score {score:.2f}",
                        hook_type="reaction_peak", score_10=0)
