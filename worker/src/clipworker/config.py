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
    """Punch-in zooms (P3). scale 1.0 = off; value from Zo / references (D022)."""
    scale: float = 1.0
    ramp_s: float = 0.2
    hold_s: float = 1.2
    min_gap_s: float = 4.0
    max_zooms: int = 8
    lead_s: float = 0.0

    @property
    def on(self) -> bool:
        return self.scale > 1.0


@dataclass(frozen=True)
class DetectorParams:
    burst_s: float = 5.0
    baseline_s: float = 600.0
    w_chat: float = 0.45
    w_unique: float = 0.20
    w_reaction: float = 0.15
    w_audio: float = 0.20
    threshold: float = 2.5
    sustain_s: float = 2.0
    cooldown_s: float = 45.0
    merge_s: float = 20.0
    pre_s: float = 25.0
    post_s: float = 15.0
    rate_floor: float = 0.5   # msgs/s floor so a quiet chat doesn't explode the ratio
    warmup_s: float = 60.0    # no triggers until this much baseline exists


@dataclass(frozen=True)
class Channel:
    key: str                  # "twitch:lacy"
    platform: str             # twitch | kick
    login: str
    streamer: str             # streamers.slug in Supabase
    layout: Layout | None
    reaction_weights: dict[str, float]
    detector: DetectorParams


@dataclass
class Settings:
    work_dir: Path
    channels: list[Channel]
    caption_style: CaptionStyle | None
    max_channels: int = 3
    zoom: ZoomParams = field(default_factory=ZoomParams)
    extra: dict = field(default_factory=dict)

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
    channels = []
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
        channels.append(Channel(f"{platform}:{c['login'].lower()}", platform,
                                c["login"].lower(), c.get("streamer", c["login"].lower()),
                                layout, weights, det))
    max_channels = int(data.get("max_channels", 3))
    if len(channels) > max_channels:
        raise ConfigError(f"{len(channels)} channels configured; max is {max_channels} "
                          "until CPU/GPU load is measured")
    style = None
    cs = data.get("caption_style")
    if cs:
        cs = {**cs, **{k: ass_colour(cs[k]) for k in
                       ("primary_colour", "highlight_colour", "outline_colour") if k in cs}}
        style = CaptionStyle(**cs)
    zoom = ZoomParams(**data.get("zoom", {}))
    if zoom.on and zoom.min_gap_s < 2 * zoom.ramp_s + zoom.hold_s:
        raise ConfigError("zoom.min_gap_s must cover one full pulse (2*ramp_s + hold_s)")
    return Settings(work_dir=work_dir, channels=channels, caption_style=style,
                    max_channels=max_channels, zoom=zoom, extra=data.get("extra", {}))


def load_settings(config_path: Path | None = None) -> Settings:
    load_dotenv(Path(env("CLIP_ENV_FILE", ".env")))
    work_dir = Path(env("CLIP_WORK_DIR", r"C:\clip-work"))
    path = config_path or Path(env("CLIP_CHANNELS_FILE", "config/channels.toml"))
    if not path.exists():
        raise ConfigError(f"channel config {path} not found (copy config/channels.example.toml)")
    with path.open("rb") as fh:
        return parse_settings(tomllib.load(fh), work_dir)
