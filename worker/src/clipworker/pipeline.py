"""Job pipeline: detected > captured > transcribed > judged > rendered > qa_passed > uploaded.

Each step is restart-safe (state in SQLite). A step that raises is retried up
to 3 times, then the job goes to `error`. Dropped candidates are logged to
Supabase candidate_log for clip-detector-tuning.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import random
import time
import uuid
from dataclasses import asdict, replace
from pathlib import Path

from . import rules
from .capture.buffer import extract_window
from .config import Channel, Crop, Layout, Settings, ass_colour, env
from .detector.deadair import dead_air_ratio, frame_reject, words_quiet
from .detector.dedupe import detection_key, same_moment
from .detector.spike import Moment
from .judge import score as score100
from .judge.grok import Judgment
from .qa import CampaignRules, check_clip
from .remote.rights import RightsGate
from .editplan import edit_overrides
from .pods import fair_order, resolve_pod_ids
from .render import recipe
from .render import tools as tools_mod
from .render.ffmpeg import render_clip
from .store import Job, Store
from .transcribe import Word, words_text

log = logging.getLogger(__name__)
MAX_ATTEMPTS = 3
CAPTURE_SLACK_S = 15.0  # wait for HLS latency + segment close before cutting


def iso(ts: float) -> str:
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).isoformat()


def dry_run_row(job: Job) -> dict:
    """What would have gone to the review queue (dry run; nothing uploaded)."""
    j = job.data.get("judgment") or {}
    m = job.data.get("manifest") or {}
    return {"job_id": job.id, "channel": job.channel, "stage": job.stage, "trigger_ts": job.trigger_ts,
            "detector_score": job.score, "title": job.data.get("title") or j.get("title"),
            "score": j.get("score"), "score_10": j.get("score_10"), "parts": j.get("parts"),
            "send_test": j.get("send_test"), "badges": j.get("badges") or job.data.get("badges"),
            "trim": [j.get("trim_in"), j.get("trim_out")], "reason": j.get("reason"),
            "video": m.get("video"), "qa": job.data.get("qa"), "dead_air": job.data.get("dead_air")}


class Pipeline:
    def __init__(self, settings: Settings, store: Store, rights: RightsGate, transcriber=None,
                 judge=None, supabase=None, clock=time.time, extract=extract_window,
                 render=render_clip, qa=check_clip, frames=None):
        self.s, self.store, self.rights = settings, store, rights
        self.transcriber, self.judge, self.sb, self.clock = transcriber, judge, supabase, clock
        self._extract, self._render, self._qa = extract, render, qa
        self._frames = frames or (lambda video, dur: frame_reject(
            video, dur, settings.dead_air, env("FFMPEG_BIN", "ffmpeg")))
        self.channels = {c.key: c for c in settings.channels}
        self._pod_ids: dict[str, str] | None = None

    def pod_of(self, channel_key: str) -> str:
        ch = self.channels.get(channel_key)
        return ch.pod if ch else "pod-1"

    def _pod_fields(self, channel_key: str) -> dict:
        """{"pod_id": ...} when [pods] enabled and the slug resolved; else {} (DB trigger falls back)."""
        if not self.s.pods.enabled or self.sb is None:
            return {}
        if self._pod_ids is None:  # resolved once (D097)
            self._pod_ids = resolve_pod_ids(self.sb, (c.pod for c in self.s.channels))
        pid = self._pod_ids.get(self.pod_of(channel_key))
        return {"pod_id": pid} if pid else {}

    # detection -> job
    def on_moment(self, m: Moment) -> str | None:
        ch = self.channels[m.channel]
        permit = self.rights.permit(ch.streamer)
        if permit is None:
            log.info("moment on %s ignored: no active campaign permits %s", ch.key, ch.streamer)
            return None
        burst = self.store.messages(ch.key, m.start_ts - 5, m.start_ts + 10)
        sample = [t for _, _, t in burst][-30:]
        job_id = uuid.uuid4().hex[:16]
        data = {"features": m.features, "peak_ts": m.peak_ts, "chat_sample": sample,
                "campaign_id": permit.campaign_id, "rules": asdict(permit.rules),
                "rules_summary": permit.rules_summary}
        if not self.store.create_job(job_id, ch.key, m.window_start, m.window_end, m.start_ts,
                                     m.peak_score, data, detection_key(ch.key, m.start_ts)):
            return None
        return job_id

    def clip_that(self, channel_key: str, now: float, seconds: float = 40.0,
                  source: str = "dashboard") -> str | None:
        """CLIP THAT (D089): Zo's pick of the last `seconds` from the buffer. Same review gate;
        the judge trims and titles it but never drops it. Labelled missed_moment (1.5)."""
        ch = self.channels.get(channel_key)
        if ch is None:
            return None
        m = Moment(channel_key, now - seconds / 2, now - seconds / 2, 0.0, now - seconds / 2,
                   now - seconds, now, {"source": f"clip_that:{source}"})
        job_id = self.on_moment(m)
        if job_id:
            self.store.patch_data(job_id, {"force_keep": True, "label": "missed_moment",
                                           "badges": ["clip_that"]})
            if self.sb is not None:
                try:
                    self.sb.insert("clip_labels", {"job_id": job_id, "streamer": ch.streamer,
                                                   "signal": "missed_moment", "weight": 1.5,
                                                   "moment_at": iso(now - seconds / 2)},
                                   on_conflict="streamer,job_id,signal", ignore_duplicates=True)
                except Exception:  # noqa: BLE001 - labels must never block a clip
                    log.warning("clip_labels write failed for %s", job_id)
        return job_id

    def take_clip_requests(self, now: float, live: set[str]) -> int:
        """Open CLIP THAT requests from Supabase -> jobs (features.clip_that). Live channels only."""
        if self.sb is None:
            return 0
        n = 0
        for r in self.sb.select("clip_requests", status="eq.open", order="requested_at.asc", limit="10"):
            key = next((c.key for c in self.s.channels if c.streamer == r["streamer"] and c.key in live), None)
            job = self.clip_that(key, now, float(r.get("seconds") or 40), r.get("source") or "dashboard") if key else None
            self.sb.update("clip_requests", {"id": r["id"]},
                           {"status": "done" if job else "failed", "job_id": job,
                            "detail": None if job else "streamer not live, not permitted or duplicate"})
            n += 1
        return n

    # driver
    def run_once(self) -> int:
        n = 0
        for stage, fn in (("detected", self._capture), ("captured", self._transcribe),
                          ("transcribed", self._judge), ("judged", self._render_step),
                          ("rendered", self._qa_step), ("qa_passed", self._upload)):
            jobs = list(self.store.jobs_in(stage))
            if self.s.pods.enabled:  # one shared GPU queue, round-robin by pod (D096)
                jobs = fair_order(jobs, lambda j: self.pod_of(j.channel))
            for job in jobs:
                try:
                    if fn(job):
                        n += 1
                except Exception as e:  # noqa: BLE001 - recorded, retried, then parked
                    log.exception("job %s failed at %s", job.id, stage)
                    if self.store.record_failure(job.id, f"{type(e).__name__}: {e}") >= MAX_ATTEMPTS:
                        self.store.advance(job.id, "error", error=str(e)[:500])
                        self._log(job, "error", f"{stage}: {e}")
        return n

    def _log(self, job: Job, outcome: str, reason: str) -> None:
        if self.sb is None:
            return
        try:
            self.sb.log_candidate({"job_id": job.id, "channel_key": job.channel,
                                   "moment_at": iso(job.trigger_ts), "score": job.score,
                                   "outcome": outcome, "reason": reason[:500],
                                   "features": job.data.get("features", {}),
                                   **self._pod_fields(job.channel)})
        except Exception:  # noqa: BLE001 - logging must never block the pipeline
            log.warning("candidate_log write failed for %s", job.id)

    def _job_dir(self, job: Job) -> Path:
        return self.s.renders_dir / job.id

    # steps (return True when the job advanced)
    def _capture(self, job: Job) -> bool:
        if self.clock() < job.end_ts + CAPTURE_SLACK_S:
            return False
        login = job.channel.split(":", 1)[1]
        cap = self._extract(self.s.buffer_dir / job.channel.replace(":", "_"), job.start_ts,
                            job.end_ts, self._job_dir(job) / "work")
        self.store.advance(job.id, "captured", {"capture": cap, "login": login})
        return True

    def _transcribe(self, job: Job) -> bool:
        words = self.transcriber.transcribe(Path(job.data["capture"]["audio"]))
        self.store.advance(job.id, "transcribed",
                           {"words": [asdict(w) for w in words], "transcript": words_text(words)})
        return True

    def _duplicate_of(self, job: Job) -> str | None:
        """Squad dedupe: same moment already kept from another channel -> drop this one."""
        for stage in ("transcribed", "judged", "rendered", "qa_passed", "uploaded"):
            for other in self.store.jobs_in(stage):
                if other.id == job.id or other.channel == job.channel:
                    continue
                if same_moment(job.trigger_ts, job.data.get("transcript", ""),
                               other.trigger_ts, other.data.get("transcript", "")):
                    return other.id
        return None

    def _judge(self, job: Job) -> bool:
        dup = self._duplicate_of(job)
        if dup:
            self.store.advance(job.id, "dropped", {"duplicate_of": dup})
            self._log(job, "duplicate", f"same moment as job {dup}")
            return True
        words = [Word(**w) for w in job.data["words"]]
        cap = job.data["capture"]
        dur = cap["end_ts"] - cap["start_ts"]
        rules = job.data["rules"]
        if self.s.features.dead_air_gate and not job.data.get("force_keep"):  # dead air costs no model call
            why = self._dead_air(job, words, dur)
            if why:
                self.store.advance(job.id, "dropped", {"dead_air": why})
                self._log(job, "dropped", why)
                return True
        # brain-only features stay out of the prompt while the brain is off (flags off = same prompt)
        hide = set() if self.s.features.brain else {"z_mood", "z_lift", "dead_air_mult"}
        j: Judgment = self.judge.judge(words, job.data["chat_sample"], {"score": job.score,
                                       **{k: v for k, v in job.data["features"].items()
                                          if isinstance(v, (int, float)) and k not in hide}},
                                       job.data["rules_summary"], dur, rules["min_s"], rules["max_s"],
                                       **({"peak_rel": job.data["peak_ts"] - cap["start_ts"]}
                                          if getattr(self.judge, "wants_peak", False) else {}))
        if j.usage and self.sb is not None:
            self.sb.log_spend("grok", self.judge.cost_usd(j.usage),
                              j.usage.get("total_tokens"), {"job_id": job.id})
        if j.keep and self.s.features.score_100:
            self._score(job, j, words, rules)
        if not j.keep and job.data.get("force_keep"):  # CLIP THAT: Zo picked it; judge only trims
            j.keep, j.reason = True, f"kept: CLIP THAT (judge said: {j.reason})"[:500]
        if not j.keep:
            self.store.advance(job.id, "dropped", {"judgment": asdict(j)})
            self._log(job, "dropped", j.reason)
            return True
        self.store.advance(job.id, "judged", {"judgment": asdict(j)})
        return True

    def _dead_air(self, job: Job, words: list[Word], dur: float) -> str | None:
        ch, p = self.channels[job.channel], self.s.dead_air
        peak_rel = job.data["peak_ts"] - job.data["capture"]["start_ts"]
        shout = float(job.data["features"].get("z_audio") or 0) >= 2.0
        if not shout and words_quiet(words, peak_rel, p) and job.score * p.quiet_mult < ch.detector.threshold:
            return "dead air: no speech or shout around the peak"
        return self._frames(Path(job.data["capture"]["video"]), dur)

    def _score(self, job: Job, j: Judgment, words: list[Word], rules: dict) -> None:
        """0-100 score (D089): measured parts in code + the judge's parts. Edits `j` in place."""
        ch = self.channels[job.channel]
        peak_rel = job.data["peak_ts"] - job.data["capture"]["start_ts"]
        meas = score100.measured(
            detector_score=job.score, history=self.store.recent_scores(job.channel, job.trigger_ts),
            threshold=ch.detector.threshold, trim_in=j.trim_in, trim_out=j.trim_out, words=words,
            peak_rel=peak_rel, hype_tokens=set(ch.reaction_weights) | {w.upper() for w in j.emphasis_words},
            min_s=rules.get("min_s", 0.0), max_s=rules.get("max_s", 1e9),
            shout=float(job.data["features"].get("z_audio") or 0) >= 2.0)
        judg = (j.parts or {}).get("judged")
        badges = list(job.data.get("badges", []))
        dar = dead_air_ratio(words, j.trim_in, j.trim_out)
        total, bonus = score100.total(meas, judg, "viewers_clipped" in badges, dar)
        j.score, j.badges = total, badges
        j.parts = {"measured": meas, "judged": judg, "bonus": bonus, "dead_air_ratio": dar}
        if judg is None:  # heuristic judge (D071): measured half only; never drops, keeps score_10 unset
            return
        j.score_10 = score100.score_10(total)
        rule = (f"score {total}/100 below {score100.DROP_BELOW}" if total < score100.DROP_BELOW else
                "no send test (nobody would share it)" if not j.send_test else "")
        if rule:
            j.keep, j.reason = False, f"rule: {rule}; {j.reason}"[:500]

    def _metadata(self, job: Job) -> tuple[str, str, list[str]]:
        j, rules = job.data["judgment"], job.data["rules"]
        tags = list(rules.get("required_tags", []))
        for t in j.get("hashtags") or []:  # judge hashtags after campaign-required ones
            if t.lower() not in {x.lower() for x in tags}:
                tags.append(t)
        title = job.data.get("title_override") or j["title"]
        desc = "\n".join([j.get("post_caption") or j["hook"], " ".join(tags)]).strip()
        return title, desc, tags

    def _render_step(self, job: Job, overrides: dict | None = None) -> bool:
        ch = self.channels[job.channel]
        # standing rules learned from Zo's notes (D078) sit under this clip's own overrides
        j = {**job.data["judgment"], **self.rule_settings(), **(overrides or {})}
        words = [Word(**w) for w in job.data["words"]]
        rec = self._recipe_for(job, j)
        if rec is not None:  # D114: the recipe sets caption style, SFX; zooms are off whatever it says
            j = {**j, **recipe.to_judgment(rec), "recipe": rec.to_json()}
        layout, track = ch.layout, ch.layout is None
        if overrides and overrides.get("layout"):
            lay = overrides["layout"]
            if lay.get("mode") == "track":  # IRL / full cam: face-tracked full frame
                layout, track = None, True
            else:
                layout = Layout(Crop(**lay["facecam"]), Crop(**lay["gameplay"]),
                                int(lay.get("facecam_height", 640)))
        crop_x = j.get("crop_x")  # kept in the judgment, so later re-renders keep Zo's crop
        if crop_x is not None:  # editor crop (D098): Zo placed a full-frame 9:16 window by hand
            layout, track = None, False
        if j.get("max_len_s"):  # hook-first, so shortening keeps the start and cuts the tail
            keep_s = max(float(j["max_len_s"]), float(job.data["rules"].get("min_s", 0)))  # campaign floor
            j["trim_out"] = min(j["trim_out"], j["trim_in"] + keep_s)
        style = self.s.caption_style
        if j.get("caption_colour") and style is not None:
            style = replace(style, highlight_colour=ass_colour(j["caption_colour"]))
        if j.get("words_per_line") and style is not None:  # editor caption mode (D098)
            style = replace(style, words_per_line=int(j["words_per_line"]))
        zoom = self.s.zoom
        if j.get("zoom") is False:
            zoom = None
        elif j.get("zoom") is True and not zoom.on:
            zoom = replace(zoom, scale=1.12)  # D077: gentle when switched on per clip
        if zoom is not None and j.get("zoom_style") == "smooth":  # D077 smooth camera, enforced
            zoom = replace(zoom, ease="smooth", moments="peak" if zoom.moments == "peak" else "emphasis",
                           scale=min(zoom.scale, 1.15) if zoom.on else zoom.scale,
                           ramp_s=max(zoom.ramp_s, 0.6), hold_s=max(zoom.hold_s, 1.6),
                           min_gap_s=max(zoom.min_gap_s, 8.0), max_zooms=min(zoom.max_zooms, 2))
        if zoom is not None and j.get("zoom_scale") is not None:  # editor slider (D098); 1.0 = off
            zoom = replace(zoom, scale=max(1.0, min(1.3, float(j["zoom_scale"]))))
        zoom = None  # D112 (Zo, 2026-11-23): no zooms on any clip, whatever the config, note or editor slider says
        sfx_on = j["sfx"] if isinstance(j.get("sfx"), bool) else self.s.sfx.enabled
        sfx = replace(self.s.sfx, enabled=sfx_on and job.data["rules"].get("allow_sfx", True))
        peak_rel = job.data["peak_ts"] - job.data["capture"]["start_ts"] - j["trim_in"]
        title, desc, tags = self._metadata(job)
        manifest = self._render(job.id, Path(job.data["capture"]["video"]), self._job_dir(job),
                                j["trim_in"], j["trim_out"], words, layout, style,
                                j.get("emphasis_words"), hook_offset=peak_rel,
                                manifest_extra={"tags": tags, "channel": job.channel,
                                                "revision": job.data.get("revision", 0)},
                                zoom=zoom, track=track, sfx=sfx,
                                **({"crop_x": float(crop_x)} if crop_x is not None else {}),
                                **({"cuts": j["cuts"]} if j.get("cuts") else {}))
        manifest = self._apply_recipe(j, manifest, peak_rel)
        self.store.advance(job.id, "rendered", {"manifest": manifest, "title": title,
                                                "description": desc, "judgment": j})
        return True

    def _recipe_for(self, job: Job, j: dict) -> "recipe.Recipe | None":
        """D114: the clip's edit recipe. Reused on re-render, else picked from the streamer's weights.
        Off (None) unless settings.extra["recipe_weights"] names the weights file."""
        path = self.s.extra.get("recipe_weights")
        if not path:
            return None
        if j.get("recipe"):
            return recipe.Recipe.from_json(j["recipe"])
        store = recipe.WeightStore(path)
        sw = store.get(job.channel)
        rec = recipe.build_recipe(job.id, job.channel, j, sw, random.Random(job.id),
                                  float(j["trim_out"]) - float(j["trim_in"]))
        recipe.record_pick(sw, rec.tools)
        store.save()
        return rec

    def _apply_recipe(self, j: dict, manifest: dict, peak_rel: float) -> dict:
        """Run the recipe's after-render effects on the finished clip and record the recipe in the manifest."""
        if not j.get("recipe"):
            return manifest
        rec = recipe.Recipe.from_json(j["recipe"])
        problems = recipe.validate(rec)
        fx = []
        if "slowmo_vignette" in rec.tools:
            fx.append({"tool": "slowmo_vignette", "at": max(0.0, peak_rel - 0.3)})
        if "music_cue" in rec.tools:
            fx.append({"tool": "music_cue", "file": self.s.extra.get("music_cue_file"), "start": 0.0})
        video = Path(manifest.get("video") or "")
        if fx and not problems and video.exists():
            manifest = {**manifest, "duration": round(tools_mod.apply_effects(
                video, fx, float(manifest["duration"]), env("FFMPEG_BIN", "ffmpeg")), 3)}
        return {**manifest, "recipe": j["recipe"], "recipe_problems": problems}

    def _qa_step(self, job: Job) -> bool:
        m = job.data["manifest"]
        res = self._qa(Path(m["video"]), self._job_dir(job) / "captions.ass",
                       CampaignRules(**job.data["rules"]), job.data["title"], job.data["description"])
        if not res.passed:
            self.store.advance(job.id, "qa_failed", {"qa": {"failures": res.failures, **res.metrics}})
            self._log(job, "qa_failed", "; ".join(res.failures))
            return True
        self.store.advance(job.id, "qa_passed", {"qa": {"failures": [], **res.metrics}})
        return True

    def _streamer_id(self, slug: str) -> str | None:
        rows = self.sb.select("streamers", slug=f"eq.{slug}", select="id")
        return rows[0]["id"] if rows else None

    def _upload(self, job: Job) -> bool:
        if self.s.features.dry_run:  # nothing leaves the PC; the job waits at qa_passed
            f = self._job_dir(job) / "dryrun.json"
            if not f.exists():
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_text(json.dumps(dry_run_row(job), indent=1), encoding="utf-8")
            return False
        if self.sb is None:
            return False
        ch = self.channels[job.channel]
        m = job.data["manifest"]
        base = f"{ch.streamer}/{job.id}"
        self.sb.upload(f"{base}/clip.mp4", Path(m["video"]), "video/mp4")
        self.sb.upload(f"{base}/thumb.jpg", Path(m["thumbnail"]), "image/jpeg")
        source_path = self._upload_source(base, m)
        j = job.data["judgment"]
        self.sb.insert("clips", {
            "job_id": job.id, "streamer_id": self._streamer_id(ch.streamer),
            "campaign_id": job.data["campaign_id"], "channel_key": job.channel,
            "state": "pending_review", "title": job.data["title"], "hook": j["hook"],
            "description": job.data["description"], "category": j["category"],
            "confidence": j["confidence"], "detector_score": job.score,
            "score_10": j.get("score_10") or None, "hook_type": j.get("hook_type"),
            "moment_at": iso(job.trigger_ts), "duration_s": m["duration"],
            "storage_path": f"{base}/clip.mp4", "thumb_path": f"{base}/thumb.jpg", "source_path": source_path,
            "qa": job.data["qa"], "judge": j, "manifest": m, **self._pod_fields(job.channel)},
            on_conflict="job_id",
            ignore_duplicates=True)
        self.store.advance(job.id, "uploaded")
        self._log(job, "kept", j.get("reason", ""))
        return True

    # --- revision memory (D078) ---------------------------------------------------------
    def rule_settings(self) -> dict:
        """Active standing rules as settings, newest per key. {} without Supabase."""
        if self.sb is None:
            return {}
        now = self.clock()
        if getattr(self, "_rules_at", 0) > now - 20:
            return self._rules
        try:
            rows = self.sb.select("edit_rules", active="eq.true", order="created_at.desc", select="*")
        except Exception as e:  # noqa: BLE001 - table missing or offline: render without rules
            log.warning("could not load edit rules: %s", e)
            rows = []
        self._rules, self._rules_at, self._rule_rows = rules.merge(rows), now, rows
        return self._rules

    def _note_edit(self, note: str, clip_id: str | None = None) -> dict:
        """Plain-English note -> settings: keyword reader, then Grok on top when a key is set.
        Cached by note text, so learning a rule and fixing the clip cost one parse."""
        cache = self.__dict__.setdefault("_note_cache", {})
        if note in cache:
            return dict(cache[note])
        edit = rules.parse_note(note)
        if self.judge is not None:
            try:
                g, usage = self.judge.parse_edit(note)
                if usage:
                    self.sb.log_spend("grok", self.judge.cost_usd(usage), usage.get("total_tokens"),
                                      {"clip_id": clip_id, "revision_note": True})
                edit.update(g)
            except Exception as e:  # noqa: BLE001 - a bad note must not block other revisions
                log.warning("could not parse revision note %r: %s", note[:80], e)
        cache[note] = dict(edit)
        return edit

    def learn_rules(self) -> int:
        """Read every new revision note; style asks become standing rules (D078)."""
        if self.sb is None:
            return 0
        n = 0
        for r in self.sb.select("revisions", learned_at="is.null", kind="eq.other",
                                order="created_at.asc", limit="50", select="*"):
            p = r.get("payload") or {}
            std = rules.standing(self._note_edit(r["note"], r["clip_id"])) if p.get("apply_all", True) else {}
            for k, v in std.items():
                self.sb.insert("edit_rules", {"key": k, "value": v, "label": rules.label(k, v),
                                              "note": r["note"][:500], "revision_id": r["id"],
                                              "clip_id": r["clip_id"], "active": True, "fixed_count": 0})
                n += 1
            self.sb.update("revisions", {"id": r["id"]}, {"learned_at": iso(self.clock())})
        if n:
            self._rules_at = 0  # reload now
            log.info("learned %d standing edit rule(s) from revision notes", n)
        return n

    def _upload_source(self, base: str, m: dict) -> str | None:
        """Before/after: the untouched 16:9 window. None when the render made none."""
        src = m.get("source_preview")
        if not src or not Path(src).exists():
            return None
        self.sb.upload(f"{base}/source.mp4", Path(src), "video/mp4")
        return f"{base}/source.mp4"

    def _rerender(self, clip: dict, job: Job, overrides: dict, title: str | None, rev: int) -> Job | None:
        """Reset the local job, render -> QA, upload over the same storage paths. None if QA failed."""
        update = {"revision": rev, **({"title_override": title} if title else {})}
        job = self.store.reset_for_revision(job.id, update)
        self._render_step(job, overrides)
        self._qa_step(self.store.job(job.id))
        job = self.store.job(job.id)
        if job.stage != "qa_passed":
            log.warning("revision %s of %s failed QA: %s", rev, clip["id"], job.data["qa"])
            return None
        m = job.data["manifest"]
        self.sb.upload(clip["storage_path"], Path(m["video"]), "video/mp4")
        self.sb.upload(clip["thumb_path"], Path(m["thumbnail"]), "image/jpeg")
        base = clip["storage_path"].rsplit("/", 1)[0]
        self.sb.update("clips", {"id": clip["id"]},
                       {"title": job.data["title"], "duration_s": m["duration"], "qa": job.data["qa"],
                        "judge": job.data["judgment"], "manifest": m, "revision": rev,
                        "source_path": self._upload_source(base, m) or clip.get("source_path")})
        self.store.advance(job.id, "uploaded")
        return job

    def recheck_queue(self, max_fix: int = 2) -> int:
        """Clips already waiting for review that break a standing rule are hidden and re-edited,
        so Zo never reviews the same defect twice (D078). Re-renders `max_fix` per call."""
        if self.sb is None:
            return 0
        settings = self.rule_settings()
        if not settings:
            return 0
        from .render.ffmpeg import MOTION_VERSION
        todo = []
        for clip in self.sb.clips_in("pending_review", limit=50):
            bad = rules.breaks(clip, settings, MOTION_VERSION)
            if not bad:
                continue
            try:
                job = self.store.job(clip["job_id"])
            except KeyError:
                continue  # footage gone: leave it for Zo
            if not clip.get("fixing"):
                self.sb.update("clips", {"id": clip["id"]}, {"fixing": {"rules": bad, "since": iso(self.clock())}})
            todo.append((clip, job, bad))
        n = 0
        for clip, job, bad in todo[:max_fix]:
            rev = int(clip.get("revision", 0)) + 1
            done = self._rerender(clip, job, {}, None, rev)
            self.sb.update("clips", {"id": clip["id"]}, {"fixing": None})
            if done is None:
                continue
            for row in getattr(self, "_rule_rows", []):
                if row["key"] in bad:
                    self.sb.update("edit_rules", {"id": row["id"]}, {"fixed_count": int(row.get("fixed_count", 0)) + 1})
            log.info("re-edited %s in review to meet rules %s", clip["id"], bad)
            n += 1
        return n

    # revise loop (publish-approval-gate step 3): re-run only what changed
    def process_revisions(self) -> int:
        if self.sb is None:
            return 0
        self.learn_rules()
        n = 0
        for clip in self.sb.clips_in("revise"):
            revs = self.sb.select("revisions", clip_id=f"eq.{clip['id']}", resolved_at="is.null",
                                  order="created_at.asc", select="*")
            if not revs:
                continue
            failed = clip.get("revise_failed") or {}
            if failed and set(failed.get("revisions") or []) == {r["id"] for r in revs}:
                continue  # these notes already failed QA; shown on the dashboard, waiting for Zo
            try:
                job = self.store.job(clip["job_id"])
            except KeyError:
                log.warning("revise for %s but local job is gone%s", clip["job_id"],
                            " (long video: revise by denying it; the next plan re-scripts)"
                            if clip.get("category") == "longform" else "")
                continue
            overrides, title = {}, None  # typed notes: trim | crop | caption | title
            for r in revs:
                p = r.get("payload") or {}
                if r["kind"] == "trim" and isinstance(p.get("edit"), dict):
                    # dashboard editor (D098): clip-relative plan -> window-relative overrides
                    base = job.data.get("judgment") or {}
                    edit, head = edit_overrides(p["edit"], float(base.get("trim_in", 0.0)),
                                                float(base.get("trim_out", clip.get("duration_s") or 0.0)),
                                                base.get("cuts"))
                    overrides.update(edit)
                    title = head or title
                elif r["kind"] == "trim":
                    overrides.update({k: float(p[k]) for k in ("trim_in", "trim_out") if k in p})
                elif r["kind"] == "crop" and "layout" in p:
                    overrides["layout"] = p["layout"]
                elif r["kind"] == "caption" and "emphasis_words" in p:
                    overrides["emphasis_words"] = list(p["emphasis_words"])
                elif r["kind"] == "title" and "title" in p:
                    title = str(p["title"])[:100]
                elif r["kind"] == "other" and r.get("note"):
                    # revision box: plain English -> settings (keywords, plus Grok when set)
                    edit = self._note_edit(r["note"], clip["id"])
                    title = edit.pop("title", None) or title
                    edit.pop("best_part_only", None)
                    overrides.update(edit)
            rev = int(clip.get("revision", 0)) + 1
            if self._rerender(clip, job, overrides, title, rev) is None:
                qa = self.store.job(job.id).data.get("qa") or {}
                self.sb.update("clips", {"id": clip["id"]}, {"revise_failed": {
                    "rev": rev, "reason": "; ".join(qa.get("failures") or [])[:300] or "render failed", "at": iso(self.clock()),
                    "revisions": [r["id"] for r in revs]}})
                continue
            if failed:
                self.sb.update("clips", {"id": clip["id"]}, {"revise_failed": None})
            self.sb.transition(clip, "pending_review", f"revision {rev}",
                               {"revisions": [r["id"] for r in revs]})
            for r in revs:
                self.sb.update("revisions", {"id": r["id"]}, {"resolved_at": iso(self.clock())})
            n += 1
        n += self.recheck_queue()
        return n
