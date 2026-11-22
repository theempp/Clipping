"""Job pipeline: detected > captured > transcribed > judged > rendered > qa_passed > uploaded.

Each step is restart-safe (state in SQLite). A step that raises is retried up
to 3 times, then the job goes to `error`. Dropped candidates are logged to
Supabase candidate_log for clip-detector-tuning.
"""
from __future__ import annotations

import datetime as dt
import logging
import time
import uuid
from dataclasses import asdict, replace
from pathlib import Path

from . import rules
from .capture.buffer import extract_window
from .config import Channel, Crop, Layout, Settings, ass_colour
from .detector.dedupe import detection_key, same_moment
from .detector.spike import Moment
from .judge.grok import Judgment
from .qa import CampaignRules, check_clip
from .remote.rights import RightsGate
from .render.ffmpeg import render_clip
from .store import Job, Store
from .transcribe import Word, words_text

log = logging.getLogger(__name__)
MAX_ATTEMPTS = 3
CAPTURE_SLACK_S = 15.0  # wait for HLS latency + segment close before cutting


def iso(ts: float) -> str:
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).isoformat()


class Pipeline:
    def __init__(self, settings: Settings, store: Store, rights: RightsGate, transcriber=None,
                 judge=None, supabase=None, clock=time.time, extract=extract_window,
                 render=render_clip, qa=check_clip):
        self.s, self.store, self.rights = settings, store, rights
        self.transcriber, self.judge, self.sb, self.clock = transcriber, judge, supabase, clock
        self._extract, self._render, self._qa = extract, render, qa
        self.channels = {c.key: c for c in settings.channels}

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

    # driver
    def run_once(self) -> int:
        n = 0
        for stage, fn in (("detected", self._capture), ("captured", self._transcribe),
                          ("transcribed", self._judge), ("judged", self._render_step),
                          ("rendered", self._qa_step), ("qa_passed", self._upload)):
            for job in list(self.store.jobs_in(stage)):
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
                                   "features": job.data.get("features", {})})
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
        j: Judgment = self.judge.judge(words, job.data["chat_sample"], {"score": job.score,
                                       **{k: v for k, v in job.data["features"].items()
                                          if isinstance(v, (int, float))}},
                                       job.data["rules_summary"], dur, rules["min_s"], rules["max_s"],
                                       **({"peak_rel": job.data["peak_ts"] - cap["start_ts"]}
                                          if getattr(self.judge, "wants_peak", False) else {}))
        if j.usage and self.sb is not None:
            self.sb.log_spend("grok", self.judge.cost_usd(j.usage),
                              j.usage.get("total_tokens"), {"job_id": job.id})
        if not j.keep:
            self.store.advance(job.id, "dropped", {"judgment": asdict(j)})
            self._log(job, "dropped", j.reason)
            return True
        self.store.advance(job.id, "judged", {"judgment": asdict(j)})
        return True

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
        layout, track = ch.layout, ch.layout is None
        if overrides and overrides.get("layout"):
            lay = overrides["layout"]
            if lay.get("mode") == "track":  # IRL / full cam: face-tracked full frame
                layout, track = None, True
            else:
                layout = Layout(Crop(**lay["facecam"]), Crop(**lay["gameplay"]),
                                int(lay.get("facecam_height", 640)))
        if j.get("max_len_s"):  # hook-first, so shortening keeps the start and cuts the tail
            keep_s = max(float(j["max_len_s"]), float(job.data["rules"].get("min_s", 0)))  # campaign floor
            j["trim_out"] = min(j["trim_out"], j["trim_in"] + keep_s)
        style = self.s.caption_style
        if j.get("caption_colour") and style is not None:
            style = replace(style, highlight_colour=ass_colour(j["caption_colour"]))
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
        sfx_on = j["sfx"] if isinstance(j.get("sfx"), bool) else self.s.sfx.enabled
        sfx = replace(self.s.sfx, enabled=sfx_on and job.data["rules"].get("allow_sfx", True))
        peak_rel = job.data["peak_ts"] - job.data["capture"]["start_ts"] - j["trim_in"]
        title, desc, tags = self._metadata(job)
        manifest = self._render(job.id, Path(job.data["capture"]["video"]), self._job_dir(job),
                                j["trim_in"], j["trim_out"], words, layout, style,
                                j.get("emphasis_words"), hook_offset=peak_rel,
                                manifest_extra={"tags": tags, "channel": job.channel,
                                                "revision": job.data.get("revision", 0)},
                                zoom=zoom, track=track, sfx=sfx)
        self.store.advance(job.id, "rendered", {"manifest": manifest, "title": title,
                                                "description": desc, "judgment": j})
        return True

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
            "qa": job.data["qa"], "judge": j, "manifest": m}, on_conflict="job_id",
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
                if r["kind"] == "trim":
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
                continue
            self.sb.transition(clip, "pending_review", f"revision {rev}",
                               {"revisions": [r["id"] for r in revs]})
            for r in revs:
                self.sb.update("revisions", {"id": r["id"]}, {"resolved_at": iso(self.clock())})
            n += 1
        n += self.recheck_queue()
        return n
