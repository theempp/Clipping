"""Dashboard editor plan -> render overrides (D091 editor round trip).

The editor works in seconds of the clip Zo watched (0 = first rendered frame). The
renderer works in seconds of the captured window, so trims are shifted by the trim_in
of the render being revised. Splits are not rendered yet: they stay in the revision note.
"""
from __future__ import annotations

LINE_WORDS = 7  # "full line" caption mode: words per caption line


def _num(v, lo: float, hi: float) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if x != x:  # NaN
        return None
    return min(hi, max(lo, x))


def edit_overrides(plan: dict, base_in: float, base_out: float) -> tuple[dict, str | None]:
    """(overrides for Pipeline._render_step, title or None). Bad or missing fields are skipped."""
    o: dict = {}
    dur = max(0.0, base_out - base_in)
    a, b = _num(plan.get("trim_in"), 0, dur), _num(plan.get("trim_out"), 0, dur)
    if a is not None and b is not None and b - a >= 1.0:
        o["trim_in"], o["trim_out"] = round(base_in + a, 3), round(base_in + b, 3)
    cx = _num(plan.get("crop_x"), 0, 1)
    if cx is not None:
        o["crop_x"] = round(cx, 4)
    z = _num(plan.get("zoom"), 1.0, 1.3)
    if z is not None:
        o["zoom_scale"] = round(z, 3)
    style = plan.get("caption_style")
    if style == "words":
        o["words_per_line"] = 3
    elif style == "line":
        o["words_per_line"] = LINE_WORDS
    emph = plan.get("emphasis_words")
    if isinstance(emph, list):
        words = [str(w).strip().strip(".,!?\"'").lower() for w in emph]
        o["emphasis_words"] = [w for w in words if w][:12]
    head = plan.get("headline")
    title = str(head).strip()[:100] if isinstance(head, str) and head.strip() else None
    return o, title
