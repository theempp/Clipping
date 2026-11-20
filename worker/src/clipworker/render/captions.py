"""whisperX words -> ASS subtitles, word-by-word highlight (clip-render step 3).

Style values come only from CaptionStyle (built from references/, D022).
"""
from __future__ import annotations

import re

from ..config import CaptionStyle
from ..transcribe import Word

W, H = 1080, 1920
SAFE_BOTTOM = 320  # px kept clear for Shorts/X UI chrome
SIDE_MARGIN = 60   # MarginL/MarginR in the style line
GAP_BREAK_S = 0.30  # a pause this long starts a new caption group
CHAR_W = 0.62       # rough glyph width / font size for bold sans (overflow guard)
_PUNCT = (".", ",", "!", "?", ";", ":")


def ass_time(t: float) -> str:
    t = max(0.0, t)
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "(").replace("}", ")").replace("\n", " ")


def _norm(w: str) -> str:
    return re.sub(r"[^a-z0-9']", "", w.lower())


def shift_words(words: list[Word], t_in: float, t_out: float) -> list[Word]:
    """Keep words inside [t_in, t_out] and rebase to 0."""
    out = []
    for w in words:
        if w.end <= t_in or w.start >= t_out:
            continue
        out.append(Word(max(0.0, w.start - t_in), min(t_out, w.end) - t_in, w.text))
    return out


def text_width(text: str, size: int, outline: float = 0, scale: int = 100) -> float:
    """Conservative pixel width estimate for one caption line (no font file needed)."""
    return (len(text) * size * CHAR_W + 2 * outline) * max(scale, 100) / 100


def group_words(words: list[Word], style: CaptionStyle) -> list[list[Word]]:
    """2-3 words on screen at a time (clipper-video rule).

    Breaks after punctuation, on pauses >= GAP_BREAK_S, at words_per_line, and
    before a line would overflow the frame width (WrapStyle 2 never wraps, so an
    overlong line is cut off at the frame edge).
    """
    n = max(1, style.words_per_line)
    usable = W - 2 * SIDE_MARGIN
    groups: list[list[Word]] = []
    cur: list[Word] = []
    for w in words:
        if cur:
            gap = w.start - cur[-1].end
            line = " ".join(x.text for x in cur + [w])
            if (len(cur) >= n or gap >= GAP_BREAK_S or cur[-1].text.rstrip().endswith(_PUNCT)
                    or text_width(line, style.size, style.outline, style.pop_scale) > usable):
                groups.append(cur)
                cur = []
        cur.append(w)
    if cur:
        groups.append(cur)
    return groups


def build_ass(words: list[Word], style: CaptionStyle, emphasis: list[str] | None = None) -> str:
    if style.margin_v < SAFE_BOTTOM:
        raise ValueError(f"caption margin_v {style.margin_v} is inside the platform UI safe area "
                         f"(< {SAFE_BOTTOM}px)")
    emph = {_norm(e) for e in (emphasis or [])}
    header = (
        "[Script Info]\nScriptType: v4.00+\n"
        f"PlayResX: {W}\nPlayResY: {H}\nWrapStyle: 2\nScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Cap,{style.font},{style.size},{style.primary_colour},{style.highlight_colour},"
        f"{style.outline_colour},&H00000000,0,0,0,0,100,100,0,0,1,{style.outline},0,2,60,60,"
        f"{style.margin_v},1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    events = []
    groups = group_words(words, style)
    emph_c = style.emphasis_colour or style.highlight_colour
    pop = ""
    if style.pop_scale != 100:
        pop = (f"{{\\fscx{style.pop_scale}\\fscy{style.pop_scale}"
               f"\\t(0,{style.pop_ms},\\fscx100\\fscy100)}}")
    for gi, g in enumerate(groups):
        group_end = g[-1].end
        if gi + 1 < len(groups):
            group_end = min(max(group_end, g[-1].end), groups[gi + 1][0].start) or g[-1].end
        for wi, w in enumerate(g):
            start = w.start
            end = g[wi + 1].start if wi + 1 < len(g) else max(group_end, w.end)
            if end <= start:
                end = start + 0.05
            parts = []
            for j, x in enumerate(g):
                t = _esc(x.text)
                is_emph = _norm(x.text) in emph
                if j == wi:
                    t = pop + "{\\c" + style.highlight_colour + "}" + t
                    if pop:  # reset scale so the rest of the line stays 100%
                        t += "{\\fscx100\\fscy100}"
                    t += "{\\c" + style.primary_colour + "}"
                elif is_emph:
                    t = "{\\c" + emph_c + "}" + t + "{\\c" + style.primary_colour + "}"
                if is_emph:
                    t = "{\\b1}" + t + "{\\b0}"
                parts.append(t)
            events.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Cap,,0,0,0,,{' '.join(parts)}")
    return header + "\n".join(events) + "\n"


def parse_ass_events(text: str) -> list[tuple[float, float]]:
    out = []
    for line in text.splitlines():
        if line.startswith("Dialogue:"):
            f = line.split(",", 9)
            out.append((_parse_t(f[1]), _parse_t(f[2])))
    return out


def _parse_t(s: str) -> float:
    h, m, rest = s.split(":")
    return int(h) * 3600 + int(m) * 60 + float(rest)
