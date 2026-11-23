"""Dry run on a downloaded VOD (Phase 1, D089): the full pipeline for one streamer, offline.

chat JSON (TwitchDownloaderCLI format) + VOD file -> detector (with whatever flags are on)
-> capture from the file -> transcribe -> judge -> render -> QA -> stops at qa_passed.
Nothing is uploaded, posted or written to Supabase. Report: <work>/dryrun/<stamp>/report.md.
Times are VOD offsets (seconds); the pipeline clock is pinned past the end.
"""
from __future__ import annotations

import json
import subprocess
import time
from dataclasses import replace
from pathlib import Path

from . import brain
from .capture.buffer import parse_ebur128
from .config import Settings
from .detector.deadair import DeadAirGate
from .detector.replay import load_twitchdownloader_chat, replay
from .pipeline import Pipeline, dry_run_row
from .remote.rights import RightsGate
from .store import Store


def vod_extractor(vod: Path, ffmpeg: str = "ffmpeg", run=subprocess.run):
    """extract_window stand-in that cuts [start, end] (VOD offsets) straight from the file."""
    def extract(_buf_dir, start: float, end: float, out_dir: Path) -> dict:
        out_dir.mkdir(parents=True, exist_ok=True)
        start = max(0.0, start)
        video, audio = out_dir / "window.mp4", out_dir / "window.wav"
        run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{start:.3f}", "-i", str(vod),
             # crop boxes are measured on 1920x1080 live frames; a lower-res VOD is scaled up to match
             "-t", f"{end - start:.3f}", "-map", "0:v:0", "-map", "0:a:0",
             "-vf", "scale=1920:1080:flags=bicubic,setsar=1", "-c:v", "libx264",
             "-preset", "veryfast", "-crf", "16", "-c:a", "aac", "-b:a", "192k", str(video),
             "-t", f"{end - start:.3f}", "-map", "0:a:0", "-ac", "1", "-ar", "16000", str(audio)], check=True)
        return {"video": str(video), "audio": str(audio), "start_ts": start, "end_ts": end, "partial": False}
    return extract


def vod_loudness(vod: Path, ffmpeg: str = "ffmpeg", run=subprocess.run) -> list[tuple[float, float]]:
    r = run([ffmpeg, "-hide_banner", "-nostats", "-i", str(vod), "-map", "0:a:0", "-vn",
             "-filter:a", "ebur128=peak=none", "-f", "null", "-"], capture_output=True, text=True)
    return parse_ebur128((r.stderr or "").splitlines(), 0.0, step_s=0.5)


def run_dry(s: Settings, channel_key: str, vod: Path, chat: Path, out_root: Path, transcriber, judge,
            max_moments: int = 12, ffmpeg: str = "ffmpeg", loudness=None, extract=None,
            render=None, qa=None, supabase=None, vod_started_at: float = 0.0) -> Path:
    """supabase set = review mode: QA-passed clips upload as pending_review (the publisher
    is never started here, and the DB refuses to publish anything a human has not approved).
    vod_started_at (unix) turns VOD offsets into real moment times on the dashboard."""
    s = replace(s, features=replace(s.features, dry_run=supabase is None))
    ch = next(c for c in s.channels if c.key == channel_key)
    params, lift = ch.detector, None
    if s.features.brain:
        b = brain.load(s.state_dir(ch), ch.streamer)
        params, lift = brain.apply(b, ch.detector), (None if b.learning else b.chat_word_lift)
    msgs = load_twitchdownloader_chat(chat)
    loud = vod_loudness(vod, ffmpeg) if loudness is None else loudness
    gate = DeadAirGate(s.dead_air) if s.features.dead_air_gate else None
    moments, det = replay(msgs, params, ch.reaction_weights, channel=ch.key, loudness=loud,
                          gate=gate, lift=lift)
    out = Path(out_root) / time.strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    s = replace(s, work_dir=out)
    store = Store(out / "dryrun.sqlite3")
    store.add_messages((ch.key, t, u, txt) for t, u, txt in msgs)
    rights = RightsGate(lambda: [], roster={ch.streamer})
    kw = {k: v for k, v in (("render", render), ("qa", qa)) if v is not None}
    pipe = Pipeline(s, store, rights, transcriber, judge, supabase, clock=lambda: float("inf"),
                    extract=extract or vod_extractor(vod, ffmpeg), **kw)
    pipe.ts_offset = vod_started_at
    top = sorted(moments, key=lambda m: -m.peak_score)[:max_moments]
    jobs = [j for j in (pipe.on_moment(m) for m in sorted(top, key=lambda m: m.start_ts)) if j]
    for _ in range(12):
        if not pipe.run_once():
            break
    rows = [dry_run_row(store.job(j)) for j in jobs]
    rep = {"channel": ch.key, "vod": str(vod), "flags": {k: v for k, v in vars(s.features).items()},
           "candidates": len(moments), "judged": len(jobs),
           "gated": [{"start": m.start_ts, "reason": why} for m, why in det.rejected], "jobs": rows}
    (out / "report.json").write_text(json.dumps(rep, indent=1), encoding="utf-8")
    (out / "report.md").write_text(render_report(rep), encoding="utf-8")
    return out


def _hms(t) -> str:
    t = max(0, int(t or 0))
    return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}"


def render_report(rep: dict) -> str:
    kept = [r for r in rep["jobs"] if r["stage"] in ("qa_passed", "uploaded")]
    lines = [f"# Dry run: {rep['channel']} (nothing posted)",
             f"VOD: {rep['vod']}",
             "Flags on: " + (", ".join(k for k, v in rep["flags"].items() if v) or "none"),
             f"Candidates {rep['candidates']} | sent on {rep['judged']} | gated (dead air) {len(rep['gated'])} | "
             f"would reach review {len(kept)}", "",
             "| VOD time | stage | score | score_10 | title / reason |", "|---|---|---|---|---|"]
    for r in rep["jobs"]:
        what = r["title"] if r["stage"] in ("qa_passed", "uploaded") else (r.get("dead_air") or r.get("reason") or "")
        lines.append(f"| {_hms(r['trigger_ts'])} | {r['stage']} | {r['score'] if r['score'] is not None else '-'} | "
                     f"{r['score_10'] or '-'} | {str(what).replace('|', '/')[:120]} |")
    for g in rep["gated"]:
        lines.append(f"| {_hms(g['start'])} | gated | - | - | {g['reason']} |")
    return "\n".join(lines) + "\n"
