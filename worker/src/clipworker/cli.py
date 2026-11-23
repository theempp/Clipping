"""clipworker CLI.

  clipworker check                  config + env sanity, no network
  clipworker replay CHAT.json [--labels L.txt] [--channel twitch:lacy]
                                    offline detector replay/eval (no video, no model)
  clipworker live                   run everything (PC on = monitoring on)
  clipworker publish-once           one publisher pass (approved clips only)
  clipworker discord                campaign watcher bot
  clipworker longform-once          plan/script/voice/render/QA today's Zwoclipp long videos (D079-D082)
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


def cmd_dryrun(a) -> int:
    """Offline: no Supabase, no publisher. Judge = Grok if a key is set (spend!), else heuristic."""
    import httpx

    from .dryrun import run_dry
    from .judge.heuristic import HeuristicJudge
    from .transcribe import CachedTranscriber, WhisperXTranscriber
    s = load_settings(Path(a.config) if a.config else None)
    if not any(c.key == a.channel for c in s.channels):
        print(f"channel {a.channel} not in config", file=sys.stderr)
        return 2
    judge = HeuristicJudge()
    if env("XAI_API_KEY") and not a.no_judge:
        from .judge.grok import GrokJudge
        judge = GrokJudge(env("XAI_API_KEY"), env("GROK_MODEL", required=True), s.cache_dir,
                          httpx.Client(timeout=60), float(env("GROK_PRICE_IN_PER_MTOK", "0")),
                          float(env("GROK_PRICE_OUT_PER_MTOK", "0")), score_100=s.features.score_100)
    tr = CachedTranscriber(WhisperXTranscriber.auto(), s.cache_dir)
    out = run_dry(s, a.channel, Path(a.video), Path(a.chat), s.work_dir / "dryrun", tr, judge,
                  max_moments=a.max, ffmpeg=env("FFMPEG_BIN", "ffmpeg"))
    print((out / "report.md").read_text(encoding="utf-8"))
    print(f"report: {out / 'report.md'}")
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
        if env("XAI_API_KEY"):
            judge = GrokJudge(env("XAI_API_KEY"), env("GROK_MODEL", required=True), s.cache_dir,
                              httpx.Client(timeout=60), float(env("GROK_PRICE_IN_PER_MTOK", "0")),
                              float(env("GROK_PRICE_OUT_PER_MTOK", "0")),
                              score_100=s.features.score_100)
        else:  # D071: no key -> keep every moment, cut around the peak, titles say UNJUDGED
            from .judge.heuristic import HeuristicJudge
            logging.warning("XAI_API_KEY not set: clips are NOT judged (heuristic cut, UNJUDGED titles)")
            judge = HeuristicJudge()
        tr = CachedTranscriber(WhisperXTranscriber.auto(), s.cache_dir)
    # D070: roster streamers are always tracked; an active campaign is an extra
    gate = RightsGate(sb.active_campaigns, roster={c.streamer for c in s.channels})
    pipe = Pipeline(s, store, gate, tr, judge, sb)
    return s, sb, store, pipe


def _publisher(sb, store, posting=None):
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
    return PublishRunner(sb, pubs, local_video, ramp=posting if posting is not None and posting.ramp else None)


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
    sub.add_parser("longform-once")
    sub.add_parser("stuck-posts", help="flag posts with < 20 plays at ~1 h ([stats] stuck_flag)")
    sub.add_parser("scout-pods", help="suggest active campaigns per pod ([scout] per_pod)")
    d = sub.add_parser("dryrun-vod", help="full pipeline on a downloaded VOD; nothing posts")
    d.add_argument("--channel", required=True)
    d.add_argument("--video", required=True)
    d.add_argument("--chat", required=True, help="TwitchDownloaderCLI chat JSON")
    d.add_argument("--max", type=int, default=12, help="top N moments to cut")
    d.add_argument("--no-judge", action="store_true", help="heuristic cut, no Grok spend")
    bl = sub.add_parser("brain-learn", help="labels -> new brain version (features.brain)")
    bl.add_argument("--channel", required=True)
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
            on = [k for k, v in vars(s.features).items() if v]
            print("feature flags on: " + (", ".join(on) or "none"))
            for k in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "XAI_API_KEY", "GROK_MODEL",
                      "TWITCH_CLIENT_ID", "TWITCH_CLIENT_SECRET"):
                print(f"{k}: {'set' if env(k) else 'missing'}")
            return 0
        if a.cmd == "live":
            from .live import LiveRunner
            s, sb, store, pipe = _build(a)
            asyncio.run(LiveRunner(s, store, pipe, _publisher(sb, store, s.posting), sb).run())
            return 0
        if a.cmd == "stuck-posts":
            from .pods import stuck_flags
            s, sb, _, _ = _build(a, need_judge=False)
            if not s.stats.stuck_flag:
                print("[stats] stuck_flag is off")
                return 0
            for f in stuck_flags(sb.select("post_stats", hours_since_post="lte.2.5", select="*")):
                print(f"stuck: clip {f['clip_id']} {f['platform']} {f['plays']} plays at {f['hours_since_post']:g} h")
            return 0
        if a.cmd == "scout-pods":
            from .campaigns.scout import scout_pods
            s, sb, _, _ = _build(a, need_judge=False)
            if not s.scout.per_pod:
                print("[scout] per_pod is off")
                return 0
            print(f"{scout_pods(sb)} pod_campaigns row(s) suggested")
            return 0
        if a.cmd == "publish-once":
            s, sb, store, _ = _build(a, need_judge=False)
            for line in _publisher(sb, store, s.posting).run_once():
                print(line)
            return 0
        if a.cmd == "discord":
            from .campaigns.discord_bot import run_bot
            s, sb, _, _ = _build(a, need_judge=False)
            roster = [c.streamer for c in s.channels]   # D072: only the active roster counts
            gta6_only = {c.streamer for c in s.channels if c.group == "gta6_only"}
            run_bot(sb, env("DISCORD_BOT_TOKEN", required=True),
                    int(env("DISCORD_CAMPAIGN_CHANNEL_ID", required=True)), roster, set(roster), gta6_only)
            return 0
        if a.cmd == "longform-once":
            import httpx

            from .longform.runner import LongformRunner
            from .longform.script import GrokWriter
            from .longform.voice import SapiVoice
            s, sb, store, _ = _build(a, need_judge=False)
            writer = None
            if env("XAI_API_KEY"):
                writer = GrokWriter(env("XAI_API_KEY"), env("GROK_MODEL", required=True), s.cache_dir,
                                    httpx.Client(timeout=90), float(env("GROK_PRICE_IN_PER_MTOK", "0")),
                                    float(env("GROK_PRICE_OUT_PER_MTOK", "0")))
            else:
                logging.warning("XAI_API_KEY not set: long videos wait at 'planned' (no narration, no video)")
            voice = SapiVoice(env("CLIPP_TTS_VOICE") or None) if sys.platform == "win32" else None
            r = LongformRunner(s, store, writer, voice, sb)
            r.run_once()
            for pl in r.plans():
                print(f"{pl.id} {pl.tags.format}/{pl.tags.pacing}/{pl.tags.caption_style}/{pl.tags.voice}/"
                      f"{pl.tags.layout}: {pl.state}" + (f" ({pl.error})" if pl.error else ""))
            return 0
        if a.cmd == "dryrun-vod":
            return cmd_dryrun(a)
        if a.cmd == "brain-learn":
            from . import brain
            s, sb, store, _ = _build(a, need_judge=False)
            if not s.features.brain:
                print("features.brain is off: nothing learned", file=sys.stderr)
                return 2
            ch = next((c for c in s.channels if c.key == a.channel), None)
            if ch is None or not s.state_dir(ch).exists():
                print(f"{a.channel}: no channel or no streamers/<slug>/ folder", file=sys.stderr)
                return 2
            b = brain.learn(brain.load(s.state_dir(ch), ch.streamer), sb, store, ch.key, ch.detector,
                            s.state_dir(ch))
            print(brain.render_md(b))
            return 0
    except ConfigError as e:
        print(f"config error: {e}", file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":
    sys.exit(main())
