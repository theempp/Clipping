"""clipworker CLI.

  clipworker check                  config + env sanity, no network
  clipworker replay CHAT.json [--labels L.txt] [--channel twitch:lacy]
                                    offline detector replay/eval (no video, no model)
  clipworker live                   run everything (PC on = monitoring on)
  clipworker publish-once           one publisher pass (approved clips only)
  clipworker discord                campaign watcher bot
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from .config import ConfigError, DEFAULT_REACTIONS, DetectorParams, env, load_settings


def _labels(path: str | None) -> list[float]:
    if not path:
        return []
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.split("#")[0].strip()
        if not line:
            continue
        parts = [float(p) for p in line.split(":")]
        secs = 0.0
        for p in parts:
            secs = secs * 60 + p
        out.append(secs)
    return out


def cmd_replay(a) -> int:
    from .detector.replay import evaluate, load_twitchdownloader_chat, replay
    params, reactions = DetectorParams(), DEFAULT_REACTIONS
    if a.channel:
        s = load_settings(Path(a.config) if a.config else None)
        ch = next((c for c in s.channels if c.key == a.channel), None)
        if ch is None:
            print(f"channel {a.channel} not in config", file=sys.stderr)
            return 2
        params, reactions = ch.detector, ch.reaction_weights
    msgs = load_twitchdownloader_chat(Path(a.chat))
    moments, _ = replay(msgs, params, reactions)
    for m in moments:
        print(f"{_hms(m.start_ts)}  peak {m.peak_score:5.2f}  window {_hms(m.window_start)}-{_hms(m.window_end)}")
    dur = (msgs[-1][0] - msgs[0][0]) if msgs else 0
    labels = _labels(a.labels)
    if labels:
        print(evaluate(moments, labels, dur).summary())
    else:
        print(f"{len(moments)} candidates over {dur / 3600:.2f} h")
    return 0


def _hms(t: float) -> str:
    t = max(0, int(t))
    return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}"


def _build(a, need_judge=True):
    import httpx

    from .judge.grok import GrokJudge
    from .pipeline import Pipeline
    from .remote.rights import RightsGate
    from .remote.supabase import Supabase
    from .store import Store
    from .transcribe import CachedTranscriber, WhisperXTranscriber

    s = load_settings(Path(a.config) if a.config else None)
    sb = Supabase(env("SUPABASE_URL", required=True), env("SUPABASE_SERVICE_ROLE_KEY", required=True))
    store = Store(s.db_path)
    judge = tr = None
    if need_judge:
        judge = GrokJudge(env("XAI_API_KEY", required=True), env("GROK_MODEL", required=True), s.cache_dir,
                          httpx.Client(timeout=60), float(env("GROK_PRICE_IN_PER_MTOK", "0")),
                          float(env("GROK_PRICE_OUT_PER_MTOK", "0")))
        tr = CachedTranscriber(WhisperXTranscriber.auto(), s.cache_dir)
    pipe = Pipeline(s, store, RightsGate(sb.active_campaigns), tr, judge, sb)
    return s, sb, store, pipe


def _publisher(sb, store):
    import httpx

    from .publish.oauth import TokenSource
    from .publish.runner import PublishRunner
    from .publish.x import TOKEN_URL as X_TOKEN, XPublisher
    from .publish.youtube import TOKEN_URL as YT_TOKEN, YouTubePublisher

    http = httpx.Client(timeout=300)
    pubs = {}
    for d in sb.destinations():
        ref = d["credential_ref"]
        if not env(f"{ref}_CLIENT_ID"):
            logging.warning("destination %s: %s_CLIENT_ID not set; skipped", d["label"], ref)
            continue
        if d["platform"] == "youtube":
            pubs[ref] = YouTubePublisher(TokenSource(YT_TOKEN, ref, store.kv_get, store.kv_set, http), http)
        elif d["platform"] == "x":
            pubs[ref] = XPublisher(TokenSource(X_TOKEN, ref, store.kv_get, store.kv_set, http,
                                               basic_auth=True), http)

    def local_video(clip):
        return (clip.get("manifest") or {})["video"]
    return PublishRunner(sb, pubs, local_video)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="clipworker")
    p.add_argument("--config", help="channels TOML (default config/channels.toml)")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    r = sub.add_parser("replay")
    r.add_argument("chat")
    r.add_argument("--labels")
    r.add_argument("--channel")
    sub.add_parser("live")
    sub.add_parser("publish-once")
    sub.add_parser("discord")
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        if a.cmd == "replay":
            return cmd_replay(a)
        if a.cmd == "check":
            s = load_settings(Path(a.config) if a.config else None)
            print(f"work dir {s.work_dir}; {len(s.channels)} channel(s), up to {s.max_channels} captured at once")
            for grp in ("core", "gta6_only"):
                print(f"  {grp}: " + (", ".join(f"{c.key}" + (f" (GTA 6 x{c.gta6_boost:g})" if c.gta6_boost > 1 else "")
                                                for c in s.channels if c.group == grp) or "none"))
            if s.archived:
                print("  archived: " + ", ".join(c.key for c in s.archived))
            print("caption style: " + ("set" if s.caption_style else "MISSING (needs references/, D022)"))
            for k in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "XAI_API_KEY", "GROK_MODEL",
                      "TWITCH_CLIENT_ID", "TWITCH_CLIENT_SECRET"):
                print(f"{k}: {'set' if env(k) else 'missing'}")
            return 0
        if a.cmd == "live":
            from .live import LiveRunner
            s, sb, store, pipe = _build(a)
            asyncio.run(LiveRunner(s, store, pipe, _publisher(sb, store), sb).run())
            return 0
        if a.cmd == "publish-once":
            s, sb, store, _ = _build(a, need_judge=False)
            for line in _publisher(sb, store).run_once():
                print(line)
            return 0
        if a.cmd == "discord":
            from .campaigns.discord_bot import run_bot
            s, sb, _, _ = _build(a, need_judge=False)
            roster = [st["slug"] for st in sb.streamers()]
            run_bot(sb, env("DISCORD_BOT_TOKEN", required=True),
                    int(env("DISCORD_CAMPAIGN_CHANNEL_ID", required=True)), roster, set(roster))
            return 0
    except ConfigError as e:
        print(f"config error: {e}", file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":
    sys.exit(main())
