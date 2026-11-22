"""Revision memory (D078). Zo's revision notes become standing edit rules.

A note like "the zooms are too sharp, make them smoother" fixes the clip it was left on
AND becomes a rule: every later render applies it, and clips already waiting in review
that still break it are re-edited before Zo sees them. Code only: a keyword reader
turns notes into settings; the Grok edit parser (when a key is set) adds to it.
Per-clip asks (title, trim, best part only) never become rules.
"""
from __future__ import annotations

import re

# keys that describe house style, so they carry over to every clip
RULE_KEYS = ("zoom", "zoom_style", "sfx", "caption_colour", "max_len_s")

_COLOURS = {"blue": "#2F80FF", "red": "#FF3B30", "yellow": "#FFD60A", "green": "#34C759",
            "purple": "#AF52DE", "pink": "#FF5FA2", "orange": "#FF9500", "white": "#FFFFFF"}
_NEG = r"(no|stop|remove|without|don'?t|do not|get rid of|kill|turn off|less|fewer|too many)"


def parse_note(note: str) -> dict:
    """Plain-English note -> settings, by keywords. Pure function; {} when nothing matches."""
    t = " " + re.sub(r"\s+", " ", note.lower()) + " "
    out: dict = {}
    motion = re.search(r"zoom|camera|transition|robotic|choppy|jerky|smooth|harsh|hard stop|sharp", t)
    if motion:
        if re.search(_NEG + r"\b[^.]{0,20}zoom", t) and not re.search(r"\b(smooth\w*|soft\w*|eas(e|ed|ing)|clean\w*)\b", t):
            out["zoom"] = False
        else:
            out["zoom_style"] = "smooth"
    if re.search(r"sound effect|sfx|whoosh", t):
        out["sfx"] = not re.search(_NEG + r"\b[^.]{0,20}(sound effect|sfx|whoosh)", t)
    for name, hexv in _COLOURS.items():
        if re.search(rf"\b{name}\b[^.]{{0,15}}caption|caption[^.]{{0,20}}\b{name}\b", t):
            out["caption_colour"] = hexv
            break
    m = re.search(r"(under|max(?:imum)?|shorter than|less than|no longer than|at most)\s*(\d{1,3})\s*(s\b|sec|second)", t)
    if m and 3 <= int(m.group(2)) <= 180:
        out["max_len_s"] = float(m.group(2))
    return out


def standing(edit: dict) -> dict:
    """The part of a clip edit that becomes a rule for every clip."""
    return {k: edit[k] for k in RULE_KEYS if k in edit}


def label(key: str, value) -> str:
    if key == "zoom":
        return "Zoom-ins on" if value else "No zoom-ins"
    if key == "zoom_style":
        return "Smooth camera: eased zooms only on big moments"
    if key == "sfx":
        return "Sound effects on" if value else "No sound effects"
    if key == "caption_colour":
        name = next((n for n, h in _COLOURS.items() if h == value), value)
        return f"{name.capitalize()} caption highlight"
    if key == "max_len_s":
        return f"Clips {int(value)} s or shorter"
    return f"{key} = {value}"


def merge(rules: list[dict]) -> dict:
    """Active rules -> one settings dict. Rows newest first; the newest rule per key wins."""
    out: dict = {}
    for r in rules:
        if r.get("active", True) and r["key"] not in out:
            out[r["key"]] = r["value"]
    if out.get("zoom") is False:
        out.pop("zoom_style", None)
    return out


def breaks(clip: dict, settings: dict, motion_version: int) -> list[str]:
    """Which rule keys a rendered clip (row with manifest + judge) does not meet yet."""
    m = clip.get("manifest") or {}
    j = clip.get("judge") or {}
    # rendered with the rule already (it may still look off, e.g. a campaign minimum beats a max length)
    settings = {k: v for k, v in settings.items() if j.get(k) != v}
    bad = []
    zooms = m.get("zooms") or []
    if settings.get("zoom") is False and zooms:
        bad.append("zoom")
    if settings.get("zoom_style") == "smooth" and zooms and \
            int((m.get("motion") or {}).get("motion_version", 1)) < motion_version:
        bad.append("zoom_style")
    if settings.get("sfx") is False and m.get("sfx"):
        bad.append("sfx")
    if settings.get("sfx") is True and not m.get("sfx") and zooms:
        bad.append("sfx")
    c = settings.get("caption_colour")
    if c and str(j.get("caption_colour", "")).upper() != str(c).upper():
        bad.append("caption_colour")
    ml = settings.get("max_len_s")
    if ml and float(clip.get("duration_s") or m.get("duration") or 0) > float(ml) + 0.5:
        bad.append("max_len_s")
    return bad
