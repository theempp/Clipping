"""Settings: secrets from environment (.env), per-channel tuning from a TOML file.

No credential ever lives in the repo. No visual default exists (D022): caption
style must come from config built from references/, or rendering refuses.
"""
from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]   # worker/src/clipworker/config.py -> repo


class ConfigError(RuntimeError):
    pass


def load_dotenv(path: Path) -> None:
    """Minimal .env loader (KEY=VALUE, # comments). Existing env wins."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), value)


def env(name: str, default: str | None = None, *, required: bool = False) -> str | None:
    value = os.environ.get(name, default)
    if required and not value:
        raise ConfigError(f"missing required env var {name} (see worker/.env.example)")
    return value


@dataclass(frozen=True)
class Crop:
    """Crop box in source pixels."""
    x: int
    y: int
    w: int
    h: int


@dataclass(frozen=True)
class Layout:
    """Per-streamer 9:16 template: facecam on top, gameplay below (set once by hand)."""
    facecam: Crop
    gameplay: Crop
    facecam_height: int = 640  # output px of the 1920 total; gameplay gets the rest


@dataclass(frozen=True)
class CaptionStyle:
    """All values must come from references/ via Atlas (D022). No defaults on purpose."""
    font: str
    size: int
    primary_colour: str   # ASS &HAABBGGRR
    highlight_colour: str
    outline_colour: str
    outline: float
    margin_v: int
    words_per_line: int = 3
    # Optional (D022: set from references/ or leave off). 100 = no pop.
    pop_scale: int = 100            # active word starts at this % and settles to 100
    pop_ms: int = 90
    emphasis_colour: str | None = None  # judge's emphasis words; None = highlight_colour


@dataclass(frozen=True)
class ZoomParams:
    """Punch-in zooms (P3). scale 1.0 = off; value from Zo / references (D022).

    D077 (Zo, 2026-11-22): zooms read as robotic. Eased (cosine) in/out instead of linear,
    gentler, and only on moments that earn it: the detector peak plus shouted lines
    (`moments = "emphasis"`), not every sentence end. `drift` adds a slow, continuous push-in
    across the whole clip so the frame never sits dead still."""
    scale: float = 1.0
    ramp_s: float = 0.6
    hold_s: float = 1.8
    min_gap_s: float = 8.0
    max_zooms: int = 2
    lead_s: float = 0.0
    moments: str = "emphasis"   # peak | emphasis | sentences
    ease: str = "smooth"        # smooth | linear
    drift: float = 0.0          # extra scale reached by the end of the clip (0.04 = 4 %)

    @property
    def on(self) -> bool:
        return self.scale > 1.0


@dataclass(frozen=True)
class SfxParams:
    """Whoosh on each zoom (P4). Off unless enabled; the campaign can still forbid it."""
    enabled: bool = False
    volume_db: float = -18.0
    lead_s: float = 0.15          # whoosh starts this long before the zoom
    file: str | None = None       # custom sound; None = synthesized whoosh (no licence risk)


@dataclass(frozen=True)
class DetectorParams:
    burst_s: float = 5.0
    baseline_s: float = 600.0
    w_chat: float = 0.45
    w_unique: float = 0.20
    w_reaction: float = 0.15
    w_audio: float = 0.20
    w_mood: float = 0.0       # chat mood share (laugh/hype/shock); 0 = off until a brain sets it
    w_lift: float = 0.0       # learned chat-word lift; 0 = off until a brain sets it
    threshold: float = 2.5
    sustain_s: float = 2.0
    cooldown_s: float = 45.0
    merge_s: float = 20.0
    pre_s: float = 25.0
    post_s: float = 15.0
    rate_floor: float = 0.5   # msgs/s floor so a quiet chat doesn't explode the ratio
    warmup_s: float = 60.0    # no triggers until this much baseline exists


@dataclass(frozen=True)
class DeadAirParams:
    """Dead-air gate (D089, zo-clipper live-mode.md). Code only, no model."""
    show_start_window_s: float = 30.0   # show starts at the first window this long ...
    show_start_active_s: float = 8.0    # ... with at least this many seconds of voice activity
    quiet_before_s: float = 20.0        # no activity within peak-20 s .. peak+5 s = quiet
    quiet_after_s: float = 5.0
    quiet_mult: float = 0.3             # quiet moment's score is multiplied by this
    speech_range_lu: float = 6.0        # loudness proxy: momentary LUFS swing over 3 s that counts as voice
    speech_floor_lufs: float = -45.0    # ... and the loudest sample must be above this
    black_max: float = 0.5              # shortlist frame reject: share of the window that is black
    frozen_max: float = 0.6             # ... or frozen (loading screen, menu, map, BRB card)


@dataclass(frozen=True)
class Features:
    """Clipper wiring flags (docs/clipper-review/wiring-plan.md). All off by default;
    each one is reversible by flipping it back."""
    score_100: bool = False      # 0-100 score (50 measured + 50 judged); score_10 = round(score/10)
    dead_air_gate: bool = False  # show_start + quiet multiplier in the detector, frame rejects on the shortlist
    brain: bool = False          # per-streamer weights from streamers/<slug>/brain.json
    viewer_clips: bool = False   # Helix Get Clips poller: badge + positive label
    clip_that: bool = False      # CLIP THAT: last 40 s from the buffer as a labelled job
    dry_run: bool = False        # pipeline stops before Supabase upload; report written locally


@dataclass(frozen=True)
class Channel:
    key: str                  # "twitch:lacy"
    platform: str             # twitch | kick
    login: str
    streamer: str             # streamers.slug in Supabase
    layout: Layout | None
    reaction_weights: dict[str, float]
    detector: DetectorParams
    group: str = "core"       # core: every stream, GTA 6 boosted | gta6_only: only while on GTA 6
    gta6_boost: float = 1.0   # detector score multiplier while the stream's game is GTA 6
    name: str = ""            # display name for the dashboard (streamers.display_name)
    agent: str = ""           # dedicated agent, e.g. "lacy-agent" (D084); "" = none
    state_dir: str = ""       # streamer state folder (brain.json etc.); "" = streamers/<streamer>


GROUPS = ("core", "gta6_only")


@dataclass(frozen=True)
class Gta6Match:
    """How a stream's category is recognised as GTA 6 (Twitch game_id or category name)."""
    category_ids: tuple[str, ...] = ()
    name_pattern: str = r"\b(grand theft auto (vi|6)|gta ?(vi|6))\b"

    def matches(self, game_id: str | None, game_name: str | None) -> bool:
        if game_id and str(game_id) in self.category_ids:
            return True
        return bool(game_name) and re.search(self.name_pattern, game_name, re.I) is not None


@dataclass
class Settings:
    work_dir: Path
    channels: list[Channel]
    caption_style: CaptionStyle | None
    max_channels: int = 3     # max captured AT ONCE (D-plan step 9); more can be configured
    gta6: Gta6Match = field(default_factory=Gta6Match)
    archived: list[Channel] = field(default_factory=list)  # active = false: kept for their crop boxes
    zoom: ZoomParams = field(default_factory=ZoomParams)
    sfx: SfxParams = field(default_factory=SfxParams)
    extra: dict = field(default_factory=dict)
    features: Features = field(default_factory=Features)
    dead_air: DeadAirParams = field(default_factory=DeadAirParams)
    state_root: Path = REPO_ROOT / "streamers"   # where streamers/<slug>/ folders live

    def state_dir(self, ch: "Channel") -> Path:
        return Path(ch.state_dir) if ch.state_dir else self.state_root / ch.streamer

    @property
    def buffer_dir(self) -> Path: return self.work_dir / "buffer"
    @property
    def renders_dir(self) -> Path: return self.work_dir / "renders"
    @property
    def cache_dir(self) -> Path: return self.work_dir / "cache"
    @property
    def db_path(self) -> Path: return self.work_dir / "worker" / "worker.sqlite3"


DEFAULT_REACTIONS = {
    "KEKW": 1.0, "LUL": 0.8, "OMEGALUL": 1.0, "LMAO": 0.8, "??": 0.6, "W": 0.5,
    "L": 0.4, "CLIP IT": 1.5, "CLIP": 1.0, "NO WAY": 1.0, "POG": 0.8, "POGGERS": 0.8,
}


def ass_colour(value: str) -> str:
    """'#RRGGBB' -> ASS '&H00BBGGRR'; ASS values pass through unchanged."""
    v = value.strip()
    if v.startswith("&H"):
        return v
    m = re.fullmatch(r"#?([0-9a-fA-F]{6})", v)
    if not m:
        raise ConfigError(f"bad colour {value!r}: use #RRGGBB or &HAABBGGRR")
    rr, gg, bb = m.group(1)[0:2], m.group(1)[2:4], m.group(1)[4:6]
    return f"&H00{bb}{gg}{rr}".upper()


def _crop(d: dict) -> Crop:
    return Crop(int(d["x"]), int(d["y"]), int(d["w"]), int(d["h"]))


def parse_settings(data: dict, work_dir: Path) -> Settings:
    base_det = data.get("detector", {})
    g = data.get("gta6", {})
    default_boost = float(g.get("boost", 1.0))
    channels, archived = [], []
    for c in data.get("channels", []):
        layout = None
        if "layout" in c:
            lay = c["layout"]
            layout = Layout(_crop(lay["facecam"]), _crop(lay["gameplay"]),
                            int(lay.get("facecam_height", 640)))
        weights = {k.upper(): float(v) for k, v in
                   {**DEFAULT_REACTIONS, **c.get("reactions", {})}.items()}
        det = DetectorParams(**{**base_det, **c.get("detector", {})})
        platform = c["platform"].lower()
        if platform not in ("twitch", "kick"):
            raise ConfigError(f"unsupported platform {platform}")
        group = c.get("group", "core")
        if group not in GROUPS:
            raise ConfigError(f"unknown group {group!r} for {c['login']}: use one of {GROUPS}")
        boost = float(c.get("gta6_boost", default_boost if group == "core" else 1.0))
        if boost < 1.0:
            raise ConfigError(f"gta6_boost for {c['login']} must be >= 1.0")
        ch = Channel(f"{platform}:{c['login'].lower()}", platform,
                     c["login"].lower(), c.get("streamer", c["login"].lower()),
                     layout, weights, det, group, boost, c.get("name") or c["login"],
                     c.get("agent", ""), c.get("state_dir", ""))
        (channels if c.get("active", True) else archived).append(ch)
    keys = [c.key for c in channels]
    if len(keys) != len(set(keys)):
        raise ConfigError("a channel is listed twice among active channels")
    max_channels = int(data.get("max_channels", 3))
    if max_channels < 1:
        raise ConfigError("max_channels must be at least 1")
    gta6 = Gta6Match(tuple(str(i) for i in g.get("category_ids", ())),
                     g.get("name_pattern", Gta6Match.name_pattern))
    style = None
    cs = data.get("caption_style")
    if cs:
        cs = {**cs, **{k: ass_colour(cs[k]) for k in
                       ("primary_colour", "highlight_colour", "outline_colour") if k in cs}}
        style = CaptionStyle(**cs)
    zoom = ZoomParams(**data.get("zoom", {}))
    if zoom.on and zoom.min_gap_s < 2 * zoom.ramp_s + zoom.hold_s:
        raise ConfigError("zoom.min_gap_s must cover one full pulse (2*ramp_s + hold_s)")
    feats = data.get("features", {})
    unknown = set(feats) - set(Features.__dataclass_fields__)
    if unknown:
        raise ConfigError(f"unknown feature flag(s) {sorted(unknown)}")
    if any(not isinstance(v, bool) for v in feats.values()):
        raise ConfigError("feature flags must be true or false")
    return Settings(work_dir=work_dir, channels=channels, caption_style=style,
                    max_channels=max_channels, gta6=gta6, archived=archived,
                    zoom=zoom, sfx=SfxParams(**data.get("sfx", {})), extra=data.get("extra", {}),
                    features=Features(**feats), dead_air=DeadAirParams(**data.get("dead_air", {})),
                    state_root=Path(data.get("state_root") or env("CLIP_STATE_ROOT") or REPO_ROOT / "streamers"))


def load_settings(config_path: Path | None = None) -> Settings:
    load_dotenv(Path(env("CLIP_ENV_FILE", ".env")))
    work_dir = Path(env("CLIP_WORK_DIR", r"C:\clip-work"))
    path = config_path or Path(env("CLIP_CHANNELS_FILE", "config/channels.toml"))
    if not path.exists():
        raise ConfigError(f"channel config {path} not found (copy config/channels.example.toml)")
    with path.open("rb") as fh:
        return parse_settings(tomllib.load(fh), work_dir)
