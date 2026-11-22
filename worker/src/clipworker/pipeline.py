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
        j = {**job.data["judgment"], **(overrides or {})}
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
            zoom = replace(zoom, scale=1.3)  # D051 strength when switched on per clip
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
        j = job.data["judgment"]
        self.sb.insert("clips", {
            "job_id": job.id, "streamer_id": self._streamer_id(ch.streamer),
            "campaign_id": job.data["campaign_id"], "channel_key": job.channel,
            "state": "pending_review", "title": job.data["title"], "hook": j["hook"],
            "description": job.data["description"], "category": j["category"],
            "confidence": j["confidence"], "detector_score": job.score,
            "score_10": j.get("score_10") or None, "hook_type": j.get("hook_type"),
            "moment_at": iso(job.trigger_ts), "duration_s": m["duration"],
            "storage_path": f"{base}/clip.mp4", "thumb_path": f"{base}/thumb.jpg",
            "qa": job.data["qa"], "judge": j, "manifest": m}, on_conflict="job_id",
            ignore_duplicates=True)
        self.store.advance(job.id, "uploaded")
        self._log(job, "kept", j.get("reason", ""))
        return True

    # revise loop (publish-approval-gate step 3): re-run only what changed
    def process_revisions(self) -> int:
        if self.sb is None:
            return 0
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
                elif not p and r.get("note") and self.judge is not None:
                    # revision box: plain English -> settings (one small cached Grok call)
                    try:
                        edit, usage = self.judge.parse_edit(r["note"])
                    except Exception as e:  # noqa: BLE001 - a bad note must not block other revisions
                        log.warning("could not parse revision note %r: %s", r["note"][:80], e)
                        continue
                    if usage:
                        self.sb.log_spend("grok", self.judge.cost_usd(usage), usage.get("total_tokens"),
                                          {"clip_id": clip["id"], "revision_note": True})
                    title = edit.pop("title", None) or title
                    edit.pop("best_part_only", None)
                    overrides.update(edit)
            rev = int(clip.get("revision", 0)) + 1
            # reset job to judged, then re-render -> QA -> upload with the same storage path
            update = {"revision": rev, **({"title_override": title} if title else {})}
            job = self.store.reset_for_revision(job.id, update)
            self._render_step(job, overrides)
            self._qa_step(self.store.job(job.id))
            job = self.store.job(job.id)
            if job.stage != "qa_passed":
                log.warning("revision %s of %s failed QA: %s", rev, clip["id"], job.data["qa"])
                continue
            m = job.data["manifest"]
            self.sb.upload(clip["storage_path"], Path(m["video"]), "video/mp4")
            self.sb.upload(clip["thumb_path"], Path(m["thumbnail"]), "image/jpeg")
            self.sb.update("clips", {"id": clip["id"]},
                           {"title": job.data["title"], "duration_s": m["duration"], "qa": job.data["qa"],
                            "judge": job.data["judgment"], "manifest": m, "revision": rev})
            self.sb.transition(clip, "pending_review", f"revision {rev}",
                               {"revisions": [r["id"] for r in revs]})
            for r in revs:
                self.sb.update("revisions", {"id": r["id"]}, {"resolved_at": iso(self.clock())})
            self.store.advance(job.id, "uploaded")
            n += 1
        return n
