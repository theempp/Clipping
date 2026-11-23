"""Viewer-clip signal (D089; zo-clipper reference/live-mode.md). Twitch only (Kick: D041).

Helix Get Clips for the live window, same app token as the status poll. A viewer clip is
a vote that a moment mattered: we keep only its timestamp, view count and a hash of the
creator id. Never the clip file (their clip, not ours).
Match: a candidate whose trigger lies within +/-20 s of the clipped moment gets the
`viewers_clipped` badge and a positive label (0.6). A clipped moment we never caught is
a `viewer_clip` label with no job, so the brain learns what it missed.
"""
from __future__ import annotations

import datetime as dt
import hashlib
from dataclasses import dataclass

import httpx

HELIX_CLIPS_URL = "https://api.twitch.tv/helix/clips"
MATCH_S = 20.0


@dataclass(frozen=True)
class ViewerClip:
    clip_id: str
    moment_ts: float     # approx. middle of the clipped span (clips end when the viewer clicks)
    created_ts: float
    view_count: int
    creator_hash: str


def _epoch(iso: str) -> float:
    return dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()


def _iso(ts: float) -> str:
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_clips(payload: dict) -> list[ViewerClip]:
    out = []
    for d in payload.get("data", []):
        if not d.get("created_at"):
            continue
        created = _epoch(d["created_at"])
        dur = float(d.get("duration") or 30.0)
        creator = hashlib.sha256(str(d.get("creator_id", "")).encode()).hexdigest()[:16]
        out.append(ViewerClip(str(d.get("id", "")), created - dur / 2, created,
                              int(d.get("view_count") or 0), creator))
    return out


def fetch_clips(http: httpx.Client, client_id: str, token: str, broadcaster_id: str,
                started: float, ended: float, max_pages: int = 5) -> list[ViewerClip]:
    clips, cursor = [], None
    for _ in range(max_pages):
        params = {"broadcaster_id": broadcaster_id, "started_at": _iso(started),
                  "ended_at": _iso(ended), "first": "100"}
        if cursor:
            params["after"] = cursor
        r = http.get(HELIX_CLIPS_URL, params=params,
                     headers={"Client-Id": client_id, "Authorization": f"Bearer {token}"})
        r.raise_for_status()
        body = r.json()
        clips += parse_clips(body)
        cursor = (body.get("pagination") or {}).get("cursor")
        if not cursor:
            break
    return clips


def match(clip: ViewerClip, triggers: dict[str, float], tol: float = MATCH_S) -> list[str]:
    """Job ids whose trigger is within +/-tol of the clipped moment."""
    return [jid for jid, ts in triggers.items() if abs(ts - clip.moment_ts) <= tol]


def label_rows(clips: list[ViewerClip], triggers: dict[str, float], streamer: str) -> tuple[dict, list]:
    """-> ({job_id: [clip ids]}, clip_labels rows). One label per job; unmatched = missed."""
    by_job: dict[str, list[str]] = {}
    rows, seen = [], set()
    for c in clips:
        jobs = match(c, triggers)
        for jid in jobs:
            by_job.setdefault(jid, []).append(c.clip_id)
            if jid not in seen:
                seen.add(jid)
                rows.append({"job_id": jid, "streamer": streamer, "signal": "viewer_clip",
                             "weight": 0.6, "moment_at": _iso(c.moment_ts)})
        if not jobs:
            rows.append({"job_id": f"viewer:{c.clip_id}", "streamer": streamer, "signal": "viewer_clip",
                         "weight": 0.6, "moment_at": _iso(c.moment_ts),
                         "reason": f"missed: viewers clipped it ({c.view_count} views)"})
    return by_job, rows
