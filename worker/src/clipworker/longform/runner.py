"""Drive long videos for Zwoclipp: plan -> script -> voice -> render -> QA -> review queue.

Two plans a day (D082). Nothing posts: TikTok upload is manual after zo approves (D074).
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path

from ..config import Crop, Settings
from ..store import Store
from .plan import DONE_STAGES, Plan, Schedule, assemble, beat_from_job, load_schedule
from .qa_long import check_long
from .render_long import render_long
from .script import ScriptError, Writer, feasible
from .timeline import TimelineError, build
from .voice import RecordedVoice, Voice, VoiceError, voice_lines

log = logging.getLogger(__name__)
PER_DAY = 2
CHANNEL = "zwoclipp"      # channel two waits until zo brings the second account (2026-11-22)


class LongformRunner:
    def __init__(self, settings: Settings, store: Store, writer: Writer | None, ai_voice: Voice | None,
                 supabase=None, clock=time.time, render=render_long, qa=check_long,
                 logo_boxes: list[Crop] | None = None):
        self.s, self.store, self.writer, self.ai_voice, self.sb = settings, store, writer, ai_voice, supabase
        self.clock, self._render, self._qa, self.logo_boxes = clock, render, qa, logo_boxes
        self.root = settings.work_dir / "longform"
        self.root.mkdir(parents=True, exist_ok=True)
        self.channels = {c.key: c for c in settings.channels}

    # ---- persistence -------------------------------------------------------------
    def _dir(self, pid: str) -> Path:
        return self.root / pid

    def save(self, plan: Plan) -> None:
        d = self._dir(plan.id)
        d.mkdir(parents=True, exist_ok=True)
        (d / "plan.json").write_text(plan.to_json(), encoding="utf-8")

    def plans(self) -> list[Plan]:
        return [Plan.from_json(p.read_text(encoding="utf-8")) for p in sorted(self.root.glob("*/plan.json"))]

    def schedule(self) -> Schedule:
        f = self.root / "schedule.json"
        if not f.exists():   # first run starts the 4-week test today
            f.write_text(json.dumps({"start": self._today().isoformat()}), encoding="utf-8")
        return load_schedule(f)

    def _today(self) -> date:
        return datetime.fromtimestamp(self.clock(), timezone.utc).astimezone().date()

    # ---- planning ----------------------------------------------------------------
    def candidates(self):
        out = []
        for stage in DONE_STAGES:
            for job in self.store.jobs_in(stage):
                ch = self.channels.get(job.channel)
                b = beat_from_job(job, ch.streamer) if ch else None
                if b:
                    out.append(b)
        return out

    def plan_today(self) -> Plan | None:
        today = self._today().isoformat()
        existing = self.plans()
        made = [p for p in existing if p.created_at[:10] == today and p.state != "dropped"]
        if len(made) >= PER_DAY:
            return None
        used = {b.job_id for p in existing if p.state != "dropped" for b in p.beats}
        tags = self.schedule().tags_for(self._today(), len(made), CHANNEL)
        plan = assemble(self.candidates(), tags, used, self.clock())
        if plan is None:
            log.info("longform: not enough fresh moments for %s/%s yet", tags.format, tags.pacing)
            return None
        ok, why = feasible(plan)
        if not ok:
            log.info("longform: plan skipped, %s", why)
            return None
        self.save(plan)
        return plan

    # ---- steps ---------------------------------------------------------------------
    def _fail(self, plan: Plan, state: str, err: str) -> None:
        plan.state, plan.error = state, err
        self.save(plan)
        log.warning("longform %s %s: %s", plan.id, state, err)

    def step(self, plan: Plan) -> bool:
        d = self._dir(plan.id)
        try:
            if plan.state == "planned":
                if self.writer is None:
                    return False        # no model key: wait (never ship a video without narration)
                s = self.writer.write(plan)
                if s.usage and self.sb is not None and hasattr(self.writer, "cost_usd"):
                    self.sb.log_spend("grok", self.writer.cost_usd(s.usage), s.usage.get("total_tokens"),
                                      {"longform": plan.id})
                plan.script, plan.state = asdict(s), "scripted"
            elif plan.state in ("scripted", "needs_recording"):
                if plan.tags.voice == "zo":
                    voice: Voice | None = RecordedVoice(d / "recordings")
                else:
                    voice = self.ai_voice
                if voice is None:
                    return False
                try:
                    lines = voice_lines(self._script(plan), voice, d / "voice")
                except VoiceError as e:
                    if plan.state != "needs_recording":
                        self._fail(plan, "needs_recording", str(e))
                    return False
                plan.voice, plan.state = {"lines": [asdict(x) for x in lines]}, "voiced"
            elif plan.state == "voiced":
                from .voice import Line
                lines = [Line(**x) for x in plan.voice["lines"]]
                ch = self.channels.get(plan.beats[0].channel)
                layout = ch.layout if ch else None
                tl = build(plan, lines, layout is not None)
                plan.render = self._render(plan, self._script(plan), tl, layout, self.s.caption_style, d / "out")
                plan.state = "rendered"
            elif plan.state == "rendered":
                ch = self.channels.get(plan.beats[0].channel)
                sc = self._script(plan)
                res = self._qa(Path(plan.render["video"]), d / "out" / "captions.ass", plan.render,
                               ch.layout if ch else None, self.logo_boxes, sc.title, sc.caption)
                plan.qa = {"failures": res.failures, **res.metrics}
                plan.state = "qa_passed" if res.passed else "qa_failed"
            elif plan.state == "qa_passed":
                if self.sb is None or not self._upload(plan):
                    return False
                plan.state = "uploaded"
            else:
                return False
        except (ScriptError, TimelineError) as e:
            self._fail(plan, "dropped", str(e))
            return True
        self.save(plan)
        return True

    def _script(self, plan: Plan):
        from .script import Script
        return Script(**plan.script)

    def _upload(self, plan: Plan) -> bool:
        sc, m = self._script(plan), plan.render
        b0 = plan.beats[0]
        base = f"longform/{plan.id}"
        self.sb.upload(f"{base}/long.mp4", Path(m["video"]), "video/mp4")
        self.sb.upload(f"{base}/thumb.jpg", Path(m["thumbnail"]), "image/jpeg")
        rows = self.sb.select("streamers", slug=f"eq.{b0.streamer}", select="id")
        desc = "\n".join([sc.caption, " ".join(sc.hashtags)]).strip()
        clip = self.sb.insert("clips", {
            "job_id": f"long-{plan.id}", "streamer_id": rows[0]["id"] if rows else None,
            "campaign_id": None, "channel_key": b0.channel, "state": "pending_review",
            "title": sc.title, "hook": sc.hook, "description": desc, "category": "longform",
            "score_10": max(b.score_10 for b in plan.beats), "hook_type": "story_start",
            "moment_at": datetime.fromtimestamp(b0.trigger_ts, timezone.utc).isoformat(),
            "duration_s": m["duration"], "storage_path": f"{base}/long.mp4",
            "thumb_path": f"{base}/thumb.jpg", "qa": plan.qa, "judge": {"script": plan.script},
            "manifest": m}, on_conflict="job_id", ignore_duplicates=True)
        clip_id = clip[0]["id"] if clip else None
        t = plan.tags
        self.sb.insert("longform_videos", {
            "id": plan.id, "clip_id": clip_id, "channel": t.channel, "format": t.format,
            "pacing": t.pacing, "caption_style": t.caption_style, "voice": t.voice, "layout": t.layout,
            "beat_job_ids": [b.job_id for b in plan.beats], "runtime_s": m["duration"],
            "coverage": m["coverage"], "script": plan.script}, on_conflict="id", ignore_duplicates=True)
        return True

    def run_once(self) -> int:
        n = 1 if self.plan_today() else 0
        for p in self.plans():
            while self.step(p):
                n += 1
                if p.state in ("uploaded", "dropped", "qa_failed", "needs_recording"):
                    break
        return n
