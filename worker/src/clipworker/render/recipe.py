"""Edit recipe (D114): the model writes it, code renders it.

A recipe is the per-clip edit plan: layout, caption style, 3-5 tools from the shared toolbox, length,
and an optional flashback. Each streamer has weights and bans over the toolbox. The picker chooses tools
to fit the moment, never repeats a combo from the last 6 clips, and explores a lower-weight combo one clip in four.
Defaults (hard cut, headline box) are always on; extras are 0-3 tools that fit the moment.
Pure code, no model, no ffmpeg: `validate` is the gate before render and `apply_feedback` is the learn hook.
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field, asdict
from pathlib import Path

# tool -> (kind, moment tags that make it eligible; empty = always eligible)
TOOLBOX: dict[str, tuple[str, frozenset[str]]] = {
    "hard_cut": ("cut", frozenset()),          # default, always on
    "headline_box": ("caption", frozenset()),  # default, always on (D114)
    "black_spacer": ("transition", frozenset({"compilation"})),
    "slowmo_vignette": ("effect", frozenset({"punchline"})),
    "music_cue": ("music", frozenset({"mock_serious", "tense"})),
    "sfx_whoosh": ("sfx", frozenset({"reveal", "layout_swap"})),
    "sfx_hit": ("sfx", frozenset({"punchline", "reveal"})),
    "sfx_glitch": ("sfx", frozenset({"reveal", "layout_swap"})),
    "swap_full_face": ("layout", frozenset({"reaction_peak"})),
    "swap_full_game": ("layout", frozenset({"game_punchline"})),
    "gta_stinger": ("transition", frozenset({"gta6_sting"})),  # D115: GTA 6 only, a baked sting must fit
}
BANNED = frozenset({"zoom", "zoom_in", "zoom_out", "punch_in"})  # D112
MANUAL_ONLY = frozenset({"flashback"})  # D113: proposed by the agent, approved by Zo, never auto-picked

LAYOUTS = ("split", "full_face", "full_game", "track")  # track = full-frame face-tracked (IRL)
CAPTION_STYLES = ("headline", "headline+words")  # D073 A/B
DEFAULT_TOOLS = ("hard_cut", "headline_box")  # always on, listed first
MIN_TOOLS, MAX_TOOLS = 2, 5  # defaults plus 0-3 extras that fit the moment
MAX_SFX_AND_TRANSITIONS = 3  # D114: 1-3 transitions/SFX per clip
MIN_LEN_S, MAX_LEN_S = 12.0, 30.0
MIN_FONT_PX = 60  # D093
MAX_FLASHES_PER_S = 3.0  # D093
EXPLORE_EVERY = 4  # one clip in four tries a lower-weight combo
RECENT_KEEP = 6    # zo (2026-11-23): every clip must look different, so no combo repeats within the last 6


@dataclass
class Flashback:
    reason: str
    source_moment: str            # same stream or the streamer's viral clip, with a link or timestamp
    approved: bool = False        # only Zo flips this, in review


@dataclass
class Recipe:
    clip_id: str
    streamer: str
    layout: str = "split"
    caption_style: str = "headline"
    tools: list[str] = field(default_factory=list)
    length_s: float = 15.0
    longform: bool = False        # rant or compilation feeding D090 long-form
    flashback: Flashback | None = None
    explore: bool = False

    def to_json(self) -> dict:
        return asdict(self)

    @classmethod
    def from_json(cls, d: dict) -> "Recipe":
        fb = d.get("flashback")
        return cls(**{**d, "flashback": Flashback(**fb) if fb else None})


def validate(r: Recipe, font_px: int | None = None, flashes_per_s: float | None = None) -> list[str]:
    """Problems that block a render. Empty list = fine."""
    p: list[str] = []
    for t in r.tools:
        if t in BANNED:
            p.append(f"banned tool {t} (D112: no zooms)")
        elif t not in TOOLBOX:
            p.append(f"unknown tool {t}")
    if len(set(r.tools)) != len(r.tools):
        p.append("duplicate tools")
    if not MIN_TOOLS <= len(r.tools) <= MAX_TOOLS:
        p.append(f"{len(r.tools)} tools, need {MIN_TOOLS}-{MAX_TOOLS}")
    loud = [t for t in r.tools if TOOLBOX.get(t, ("",))[0] in ("sfx", "transition")]
    if len(loud) > MAX_SFX_AND_TRANSITIONS:
        p.append(f"{len(loud)} SFX/transitions, max {MAX_SFX_AND_TRANSITIONS}")
    if r.layout not in LAYOUTS:
        p.append(f"unknown layout {r.layout}")
    if r.caption_style not in CAPTION_STYLES:
        p.append(f"unknown caption_style {r.caption_style}")
    if not r.longform and not MIN_LEN_S <= r.length_s <= MAX_LEN_S:
        p.append(f"length {r.length_s}s outside {MIN_LEN_S:g}-{MAX_LEN_S:g}s")
    if r.flashback is not None and not r.flashback.approved:
        p.append("flashback not approved by Zo (D113: never automatic)")
    if font_px is not None and font_px < MIN_FONT_PX:
        p.append(f"font {font_px}px under {MIN_FONT_PX}px")
    if flashes_per_s is not None and flashes_per_s > MAX_FLASHES_PER_S:
        p.append(f"{flashes_per_s:g} flashes/s over {MAX_FLASHES_PER_S:g}")
    return p


def to_judgment(r: Recipe) -> dict:
    """Recipe -> the judgment keys the existing pipeline understands. Zooms are always off (D112)."""
    j: dict = {"zoom": False, "sfx": any(TOOLBOX.get(t, ("",))[0] == "sfx" for t in r.tools)}
    if r.caption_style == "headline+words":
        j["words_per_line"] = 3
    return j


# ---- weights (per-streamer tuning) ----

@dataclass
class StreamerWeights:
    weights: dict[str, float] = field(default_factory=dict)
    banned: set[str] = field(default_factory=set)
    last_combo: list[str] = field(default_factory=list)
    clips_made: int = 0
    strikes: dict[str, int] = field(default_factory=dict)
    recent: list[list[str]] = field(default_factory=list)  # last RECENT_KEEP combos, none may repeat

    def weight(self, tool: str) -> float:
        return self.weights.get(tool, 1.0)


class WeightStore:
    """JSON file, one StreamerWeights per streamer. Missing file or streamer = all weights 1."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.data: dict[str, StreamerWeights] = {}
        if self.path.exists():
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            for name, d in raw.items():
                self.data[name] = StreamerWeights(d.get("weights", {}), set(d.get("banned", [])),
                                                  d.get("last_combo", []), d.get("clips_made", 0),
                                                  d.get("strikes", {}), d.get("recent", []))

    def get(self, streamer: str) -> StreamerWeights:
        return self.data.setdefault(streamer, StreamerWeights())

    def save(self) -> None:
        out = {n: {"weights": w.weights, "banned": sorted(w.banned), "last_combo": w.last_combo,
                   "clips_made": w.clips_made, "strikes": w.strikes, "recent": w.recent} for n, w in self.data.items()}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(out, indent=2, sort_keys=True), encoding="utf-8")


def _eligible(sw: StreamerWeights, moment_tags: set[str]) -> list[str]:
    return [t for t, (_, tags) in TOOLBOX.items()
            if t not in sw.banned and (not tags or tags & moment_tags)]


def _sample(pool: list[str], weight_of, k: int, rng: random.Random) -> list[str]:
    pool, out = list(pool), []
    while pool and len(out) < k:
        ws = [max(weight_of(t), 0.01) for t in pool]
        t = rng.choices(pool, ws)[0]
        out.append(t)
        pool.remove(t)
    return out


def pick_tools(sw: StreamerWeights, moment_tags: set[str], rng: random.Random,
               explore: bool | None = None) -> tuple[list[str], bool]:
    """2-5 tools fitting the moment. Never the same combo as last time. Returns (tools, explored).
    Explore (default: every 4th clip) favours low-weight tools instead of high-weight ones."""
    if explore is None:
        explore = (sw.clips_made + 1) % EXPLORE_EVERY == 0
    base = [t for t in DEFAULT_TOOLS if t not in sw.banned]
    pool = [t for t in _eligible(sw, moment_tags) if t not in DEFAULT_TOOLS]
    weight_of = (lambda t: 1.0 / max(sw.weight(t), 0.01)) if explore else sw.weight
    prev = [sorted(c) for c in (sw.recent or ([sw.last_combo] if sw.last_combo else []))]
    for _ in range(20):
        k = rng.randint(1, MAX_TOOLS - len(DEFAULT_TOOLS))
        picked = _sample(pool, weight_of, min(k, len(pool)), rng)
        combo = [*base, *picked]
        loud = [t for t in combo if TOOLBOX[t][0] in ("sfx", "transition")]
        while len(loud) > MAX_SFX_AND_TRANSITIONS:
            combo.remove(loud.pop())
        if sorted(combo) not in prev:
            return combo, explore
    return combo, explore  # a tiny pool (few fitting tools) can force a repeat


def record_pick(sw: StreamerWeights, tools: list[str]) -> None:
    sw.last_combo = list(tools)
    sw.recent = [*sw.recent, list(tools)][-RECENT_KEEP:]
    sw.clips_made += 1


# ---- learn hook ----

STEP = 0.15
LO, HI = 0.2, 3.0


def apply_feedback(sw: StreamerWeights, tools: list[str], outcome: str,
                   removed: list[str] | None = None, bad_tool: str | None = None) -> None:
    """Zo's review outcome -> weights. outcome: approved_clean | approved_with_note | rejected | manual_edit.
    removed: tools Zo deleted in the manual editor (strong negative). bad_tool: a tool Zo named in a note;
    two such notes ban it."""
    delta = {"approved_clean": STEP, "approved_with_note": 0.0, "rejected": -STEP,
             "manual_edit": 0.0}.get(outcome)
    if delta is None:
        raise ValueError(f"unknown outcome {outcome}")
    for t in tools:
        if t in DEFAULT_TOOLS:
            continue
        sw.weights[t] = min(HI, max(LO, sw.weight(t) + delta))
    for t in removed or []:
        sw.weights[t] = max(LO, sw.weight(t) - 2 * STEP)
    if bad_tool:
        sw.weights[bad_tool] = max(LO, sw.weight(bad_tool) - 2 * STEP)
        sw.strikes[bad_tool] = sw.strikes.get(bad_tool, 0) + 1
        if sw.strikes[bad_tool] >= 2:
            sw.banned.add(bad_tool)


# ---- from judgment to recipe ----

def moment_tags(j: dict) -> set[str]:
    """Judge output -> the moment tags that decide which tools fit. Conservative: no tags, no extras."""
    tags: set[str] = set()
    cat, hook = j.get("category"), j.get("hook_type")
    if cat in ("funny", "fail", "rage", "clutch"):
        tags.add("punchline")
    if cat in ("reaction", "wholesome", "funny") or hook == "reaction_peak":
        tags.add("reaction_peak")
    if hook == "play_peak" or cat in ("clutch", "fail"):
        tags.add("game_punchline")
    if cat == "drama":
        tags |= {"tense", "mock_serious"}
    if j.get("compilation"):
        tags.add("compilation")
    if j.get("gta6") and cat in ("fail", "rage", "clutch", "funny"):  # a sting in stingers.STINGS fits
        tags.add("gta6_sting")
    return tags


def build_recipe(clip_id: str, streamer: str, j: dict, sw: StreamerWeights, rng: random.Random,
                 length_s: float) -> Recipe:
    tools, explored = pick_tools(sw, moment_tags(j), rng)
    layout = "split"
    if "swap_full_face" in tools and "swap_full_game" in tools:
        tools.remove("swap_full_game")  # one layout swap per clip
    style = "headline+words" if rng.random() < 0.5 else "headline"  # D073 A/B, tagged for learning
    return Recipe(clip_id=clip_id, streamer=streamer, layout=layout, caption_style=style, tools=tools,
                  length_s=round(length_s, 2), explore=explored)
