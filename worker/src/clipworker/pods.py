"""Pods Phase 1 helpers (docs/pods/build-plan.md). Pure where possible; flags off = unused."""
from __future__ import annotations

import logging
from collections import OrderedDict, defaultdict
from typing import Callable, Iterable, TypeVar

log = logging.getLogger(__name__)
T = TypeVar("T")
GPU_STAGES = ("detected", "captured", "transcribed", "judged", "rendered")


def resolve_pod_ids(sb, slugs: Iterable[str]) -> dict[str, str]:
    """slug -> pods.id, read once. {} on any failure: inserts then omit pod_id and the DB
    trigger falls back to the streamer's pod (D097)."""
    want = sorted(set(slugs))
    if sb is None or not want:
        return {}
    try:
        rows = sb.select("pods", slug=f"in.({','.join(want)})", select="id,slug")
    except Exception as e:  # noqa: BLE001
        log.warning("pod lookup failed (%s); inserts omit pod_id", e)
        return {}
    return {r["slug"]: r["id"] for r in rows if r.get("slug") in want}


def fair_order(jobs: Iterable[T], pod_of: Callable[[T], str]) -> list[T]:
    """Round-robin by pod over pending jobs, oldest-first within a pod (D096). Pods take
    turns in order of their oldest job, so one busy pod can't starve the others."""
    queues: "OrderedDict[str, list[T]]" = OrderedDict()
    for j in jobs:
        queues.setdefault(pod_of(j), []).append(j)
    out, lists = [], list(queues.values())
    for i in range(max((len(q) for q in lists), default=0)):
        out.extend(q[i] for q in lists if i < len(q))
    return out


def queue_waits(rows: Iterable[tuple[str, float]], pod_of: Callable[[str], str], now: float) -> dict[str, float]:
    """rows: (channel_key, created_at) of jobs still waiting on the GPU -> {pod: oldest wait s}."""
    out: dict[str, float] = {}
    for ch, created in rows:
        p = pod_of(ch)
        out[p] = max(out.get(p, 0.0), round(max(0.0, now - float(created)), 1))
    return out


# --- D088 posting ramp ------------------------------------------------------------------
RAMP_MAX_DAILY = 8       # D088 ceiling after the first 3 days
MIN_GAP_H = 2.5          # D088 min gap between posts on one destination


def ramp_allows(posted_ts: Iterable[float], now: float, *, ramp_daily: int, daily_cap: int,
                min_gap_h: float = MIN_GAP_H) -> tuple[bool, str]:
    """posted_ts: epoch seconds of this destination's posts in the last 24 h. ramp_daily is the
    manual step-up value (4 on days 1-3, then up to 8; never automatic). Never above daily_cap (D043)."""
    ts = sorted(float(t) for t in posted_ts if now - float(t) < 86400)
    limit = min(int(ramp_daily), RAMP_MAX_DAILY, int(daily_cap))
    if len(ts) >= limit:
        return False, f"ramp: {len(ts)}/{limit} posts in 24 h"
    gap = max(float(min_gap_h), MIN_GAP_H) * 3600
    if ts and now - ts[-1] < gap:
        return False, f"ramp: last post {(now - ts[-1]) / 3600:.1f} h ago (min {gap / 3600:g} h)"
    return True, ""


# --- stuck posts (Phase 1 stats) --------------------------------------------------------
STUCK_PLAYS = 20


def _reading(rows: list[dict], lo: float, hi: float, target: float) -> dict | None:
    near = [r for r in rows if lo <= float(r["hours_since_post"]) < hi and r.get("plays") is not None]
    return min(near, key=lambda r: abs(float(r["hours_since_post"]) - target)) if near else None


def stuck_flags(rows: Iterable[dict]) -> list[dict]:
    """post_stats rows -> one flag per (clip, platform) with < 20 plays at ~1 h, or at the ~2 h
    reading when there is no 1 h one. Flags only; nothing is deleted."""
    by: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        by[(r["clip_id"], r["platform"])].append(r)
    out = []
    for (clip, platform), rs in by.items():
        r = _reading(rs, 0.5, 1.5, 1.0) or _reading(rs, 1.5, 2.5, 2.0)
        if r is not None and int(r["plays"]) < STUCK_PLAYS:
            out.append({"clip_id": clip, "platform": platform, "plays": int(r["plays"]),
                        "hours_since_post": float(r["hours_since_post"]), "reason": f"< {STUCK_PLAYS} plays"})
    return out
