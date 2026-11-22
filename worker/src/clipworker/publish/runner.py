"""Publisher loop (publish-approval-gate).

approved -> scheduled -> published | failed. Only clips a human approved are
read. One `publications` row per clip x destination is the idempotency key:
  posted   -> never posted again
  posting  -> left over from a crash: outcome unknown, so we do NOT retry
              automatically (could double-post); marked failed for Zo to check
  failed   -> retried only if the error was retryable and attempts < 3
Daily caps per destination are checked before every call. Posting a clip that
belongs to a campaign opens the 30-min Content Rewards countdown (DB trigger).
"""
from __future__ import annotations

import datetime as dt
import logging
from pathlib import Path

from ..remote.supabase import Supabase
from .base import PublishError, Publisher

log = logging.getLogger(__name__)
MAX_ATTEMPTS = 3


def pick_destinations(clip: dict, destinations: list[dict], campaign_platforms: list[str]) -> list[dict]:
    """Dedicated account for the clip's streamer wins per platform; else shared."""
    out = {}
    for d in destinations:
        if not d.get("active", True):
            continue
        if campaign_platforms and d["platform"] not in campaign_platforms:
            continue
        sid = d.get("streamer_id")
        if sid and sid != clip.get("streamer_id"):
            continue
        cur = out.get(d["platform"])
        if cur is None or (sid and not cur.get("streamer_id")):
            out[d["platform"]] = d
    return list(out.values())


def _today_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).date().isoformat()


class PublishRunner:
    def __init__(self, sb: Supabase, publishers: dict[str, Publisher], local_video,
                 retry_backoff_s: float = 300, clock=None):
        """publishers: credential_ref -> Publisher. local_video(clip) -> Path."""
        import time
        self.sb, self.publishers, self.local_video = sb, publishers, local_video
        self.backoff, self.clock = retry_backoff_s, clock or time.time
        self._last_try: dict[str, float] = {}

    def _posted_today(self, dest_id: str) -> int:
        rows = self.sb.select("publications", destination_id=f"eq.{dest_id}", status="eq.posted",
                              posted_at=f"gte.{_today_utc()}", select="id")
        return len(rows)

    def _campaign_platforms(self, clip: dict) -> list[str]:
        if not clip.get("campaign_id"):
            return []
        rows = self.sb.select("campaigns", id=f"eq.{clip['campaign_id']}", select="platforms")
        return list(rows[0].get("platforms") or []) if rows else []

    def run_once(self) -> list[str]:
        done, now = [], self.clock()
        for clip in self.sb.clips_in("approved"):
            if clip.get("category") == "longform":
                continue   # TikTok long videos stay approved; zo uploads them by hand (D074, D075)
            clip = self.sb.transition(clip, "scheduled", "publisher picked up")
            self._last_try[clip["id"]] = now
            done.append(self.publish_clip(clip))
        for clip in self.sb.clips_in("failed"):
            if now - self._last_try.get(clip["id"], float("-inf")) < self.backoff:
                continue
            if self._retryable(clip):
                self._last_try[clip["id"]] = now
                clip = self.sb.transition(clip, "scheduled", "retry")
                done.append(self.publish_clip(clip))
        return done

    def _retryable(self, clip: dict) -> bool:
        pubs = self.sb.select("publications", clip_id=f"eq.{clip['id']}", select="*")
        bad = [p for p in pubs if p["status"] != "posted"]
        return bool(bad) and all(p["status"] == "failed" and p["attempts"] < MAX_ATTEMPTS
                                 and (p.get("response") or {}).get("retryable") for p in bad)

    def publish_clip(self, clip: dict) -> str:
        dests = pick_destinations(clip, self.sb.destinations(), self._campaign_platforms(clip))
        if not dests:
            self.sb.transition(clip, "failed", "no active destination for this clip")
            return f"{clip['id']}: failed (no destination)"
        errors = []
        for d in dests:
            try:
                self._publish_one(clip, d)
            except PublishError as e:
                errors.append(f"{d['platform']}: {e}")
        if errors:
            self.sb.transition(clip, "failed", "; ".join(errors)[:500])
            return f"{clip['id']}: failed ({'; '.join(errors)})"
        self.sb.transition(clip, "published", f"posted to {', '.join(d['platform'] for d in dests)}")
        return f"{clip['id']}: published"

    def _publish_one(self, clip: dict, d: dict) -> None:
        row = self.sb.insert("publications", {"clip_id": clip["id"], "destination_id": d["id"]},
                             on_conflict="clip_id,destination_id", ignore_duplicates=True)
        pub = (row or self.sb.select("publications", clip_id=f"eq.{clip['id']}",
                                     destination_id=f"eq.{d['id']}", select="*"))[0]
        if pub["status"] == "posted":
            return
        if pub["status"] == "posting":
            self.sb.update("publications", {"id": pub["id"]},
                           {"status": "failed", "last_error": "interrupted mid-post; check platform "
                            "before retrying", "response": {"retryable": False}})
            raise PublishError("previous attempt interrupted; outcome unknown (no auto-retry)")
        if pub["attempts"] >= MAX_ATTEMPTS:
            raise PublishError("max attempts reached")
        if self._posted_today(d["id"]) >= int(d.get("daily_cap", 10)):
            raise PublishError(f"daily cap {d.get('daily_cap')} reached for {d['label']}", retryable=True)
        pub_impl = self.publishers.get(d["credential_ref"])
        if pub_impl is None:
            raise PublishError(f"no credentials loaded for {d['credential_ref']}")
        self.sb.update("publications", {"id": pub["id"]},
                       {"status": "posting", "attempts": pub["attempts"] + 1})
        meta = clip.get("manifest") or {}
        try:
            res = pub_impl.post(Path(self.local_video(clip)), clip.get("title") or "",
                                clip.get("description") or "", list(meta.get("tags", [])))
        except PublishError as e:
            self.sb.update("publications", {"id": pub["id"]},
                           {"status": "failed", "last_error": str(e)[:500],
                            "response": {"retryable": e.retryable}})
            raise
        except Exception as e:  # network etc: outcome unknown only if the call may have landed
            self.sb.update("publications", {"id": pub["id"]},
                           {"status": "failed", "last_error": f"{type(e).__name__}: {e}"[:500],
                            "response": {"retryable": False}})
            raise PublishError(str(e)) from e
        self.sb.update("publications", {"id": pub["id"]},
                       {"status": "posted", "external_id": res.external_id, "url": res.url,
                        "posted_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                        "response": {"id": res.external_id}})
        if res.cost_usd:
            self.sb.log_spend("x_post" if d["platform"] == "x" else "other", res.cost_usd,
                              1, {"clip_id": clip["id"]})
