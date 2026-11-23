"""Dashboard editor plan -> render overrides (D098 editor round trip).

The editor works in seconds of the clip Zo watched (0 = first rendered frame). The
renderer works in seconds of the captured window, so trims are shifted by the trim_in
of the render being revised. If that render already had cuts, clip time is mapped back
through the kept pieces. Dropped segments (between splits) become window-relative `cuts`;
a new list of cuts replaces the old one.
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


def _kept(base_in: float, base_out: float, cuts) -> list[tuple[float, float]]:
    pieces, t = [], base_in
    for c in sorted(cuts or []):
        a, b = max(base_in, float(c[0])), min(base_out, float(c[1]))
        if b <= a:
            continue
        if a > t:
            pieces.append((t, a))
        t = max(t, b)
    if base_out > t:
        pieces.append((t, base_out))
    return pieces or [(base_in, base_out)]


def to_window(t: float, pieces: list[tuple[float, float]]) -> float:
    """Clip-relative seconds (what Zo saw) -> capture-window seconds."""
    for a, b in pieces:
        if t <= b - a:
            return a + t
        t -= b - a
    return pieces[-1][1]


def edit_overrides(plan: dict, base_in: float, base_out: float,
                   base_cuts: list | None = None) -> tuple[dict, str | None]:
    """(overrides for Pipeline._render_step, title or None). Bad or missing fields are skipped."""
    o: dict = {}
    pieces = _kept(base_in, base_out, base_cuts)
    dur = sum(b - a for a, b in pieces)
    a, b = _num(plan.get("trim_in"), 0, dur), _num(plan.get("trim_out"), 0, dur)
    if a is not None and b is not None and b - a >= 1.0:
        o["trim_in"], o["trim_out"] = round(to_window(a, pieces), 3), round(to_window(b, pieces), 3)
    cuts = []
    for c in plan.get("cuts") or []:
        if isinstance(c, (list, tuple)) and len(c) == 2:
            x, y = _num(c[0], 0, dur), _num(c[1], 0, dur)
            if x is not None and y is not None and y - x >= 0.2:
                cuts.append([round(to_window(x, pieces), 3), round(to_window(y, pieces), 3)])
    if "cuts" in plan:  # a new list replaces earlier cuts; absent = earlier cuts (window seconds) stay
        o["cuts"] = cuts
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
