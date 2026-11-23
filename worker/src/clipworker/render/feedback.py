"""Review outcome and notes -> recipe weights (D114 learning loop). Pure functions, no I/O."""
from __future__ import annotations

import re

# words in a note that name a tool (any of these -> that tool)
TOOL_WORDS: dict[str, tuple[str, ...]] = {
    "slowmo_vignette": ("slow mo", "slowmo", "slow-mo", "slow motion", "vignette", "dark edges"),
    "music_cue": ("music", "song", "choir", "background track"),
    "black_spacer": ("black frame", "black screen", "black flash", "spacer", "blackout"),
    "sfx_hit": ("hit sound", "impact", "boom", "bass drop"),
    "sfx_glitch": ("glitch",),
    "sfx_whoosh": ("whoosh", "swoosh"),
    "swap_full_face": ("full face", "face swap", "face cut", "cut to face"),
    "swap_full_game": ("full game", "game cut", "cut to game"),
}
GENERIC_SFX = ("sound effect", "sound effects", "sfx", "sounds")
SFX_TOOLS = ("sfx_hit", "sfx_glitch", "sfx_whoosh")
NEGATIVE = re.compile(r"\b(no|not|don'?t|dont|remove|without|stop|less|too much|too many|too loud|hate|"
                      r"annoying|cut the|get rid|drop the|skip|never|lose the|turn off)\b")


def tools_to_avoid(note: str, tools_in_clip: list[str] | None = None) -> list[str]:
    """Tools a negative note points at. A generic 'no sound effects' blames the SFX tools the clip used."""
    n = " ".join(note.lower().split())
    if not NEGATIVE.search(n):
        return []
    hit = [t for t, ws in TOOL_WORDS.items() if any(w in n for w in ws)]
    if any(w in n for w in GENERIC_SFX):
        used = [t for t in (tools_in_clip or SFX_TOOLS) if t in SFX_TOOLS]
        hit += [t for t in used if t not in hit]
    return hit


def outcome(state: str, n_revisions: int) -> str | None:
    """Final clip state -> apply_feedback outcome. None = not final yet, learn later."""
    if state == "rejected":
        return "rejected"
    if state in ("approved", "scheduled", "published"):
        return "approved_clean" if n_revisions == 0 else "approved_with_note"
    return None
