"""Pods Phase 1: config flags, pod resolve, fair queue, D088 ramp, stuck flags, per-pod scout."""
from pathlib import Path

from clipworker.campaigns.scout import scout_pods
from clipworker.config import parse_settings
from clipworker.pods import fair_order, queue_waits, ramp_allows, resolve_pod_ids, stuck_flags

H = 3600.0


def test_flags_default_off_and_pod_default():
    s = parse_settings({"channels": [{"platform": "twitch", "login": "Lacy"},
                                     {"platform": "kick", "login": "b", "pod": "pod-2"}]}, Path("."))
    assert not (s.pods.enabled or s.posting.ramp or s.stats.stuck_flag or s.scout.per_pod)
    assert [c.pod for c in s.channels] == ["pod-1", "pod-2"]
    s = parse_settings({"pods": {"enabled": True}, "posting": {"ramp": True, "ramp_daily": 8}}, Path("."))
    assert s.pods.enabled and s.posting.ramp_daily == 8


class _SB:
    def __init__(self, rows=None, boom=False):
        self.rows, self.boom, self.calls = rows or [], boom, 0

    def select(self, table, **p):
        self.calls += 1
        if self.boom:
            raise RuntimeError("down")
        return self.rows


def test_resolve_pod_ids_and_failure():
    assert resolve_pod_ids(_SB([{"id": "u1", "slug": "pod-1"}]), ["pod-1", "pod-1"]) == {"pod-1": "u1"}
    assert resolve_pod_ids(_SB(boom=True), ["pod-1"]) == {}
    assert resolve_pod_ids(None, ["pod-1"]) == {}


def test_fair_order_round_robin():
    jobs = [("a", 1), ("a", 2), ("a", 3), ("b", 1), ("c", 1), ("b", 2)]
    out = fair_order(jobs, lambda j: j[0])
    assert out == [("a", 1), ("b", 1), ("c", 1), ("a", 2), ("b", 2), ("a", 3)]
    assert fair_order([], lambda j: j) == []


def test_queue_waits_oldest_per_pod():
    pods = {"twitch:x": "pod-1", "twitch:y": "pod-2"}
    w = queue_waits([("twitch:x", 90), ("twitch:x", 50), ("twitch:y", 95)], pods.get, 100)
    assert w == {"pod-1": 50.0, "pod-2": 5.0}


def test_ramp_gap_and_caps():
    now = 100 * H
    assert ramp_allows([], now, ramp_daily=4, daily_cap=10) == (True, "")
    assert not ramp_allows([now - 2.4 * H], now, ramp_daily=4, daily_cap=10)[0]
    assert ramp_allows([now - 2.5 * H], now, ramp_daily=4, daily_cap=10)[0]
    four = [now - k * 3 * H for k in range(1, 5)]
    assert not ramp_allows(four, now, ramp_daily=4, daily_cap=10)[0]
    assert ramp_allows(four, now, ramp_daily=8, daily_cap=10)[0]
    assert not ramp_allows(four, now, ramp_daily=8, daily_cap=3)[0]       # never above D043 cap
    assert not ramp_allows(four * 3, now, ramp_daily=50, daily_cap=50)[0]  # 8 ceiling
    assert not ramp_allows([now - 2 * H], now, ramp_daily=8, daily_cap=10, min_gap_h=1)[0]  # gap floor 2.5 h
    assert ramp_allows([now - 30 * H] * 9, now, ramp_daily=4, daily_cap=10)[0]  # older than 24 h ignored


def test_ramp_simulated_day_gaps():
    now, posted = 0.0, []
    while now < 24 * H:
        if ramp_allows(posted, now, ramp_daily=8, daily_cap=10)[0]:
            posted.append(now)
        now += 600
    assert len(posted) <= 8
    assert all(b - a >= 2.5 * H for a, b in zip(posted, posted[1:]))


def test_stuck_flags():
    rows = [
        {"clip_id": "c1", "platform": "x", "hours_since_post": 1.0, "plays": 12},
        {"clip_id": "c1", "platform": "x", "hours_since_post": 2.0, "plays": 400},
        {"clip_id": "c2", "platform": "youtube", "hours_since_post": 2.1, "plays": 5},   # no 1 h reading
        {"clip_id": "c3", "platform": "x", "hours_since_post": 0.9, "plays": 500},
        {"clip_id": "c4", "platform": "x", "hours_since_post": 0.1, "plays": 0},          # too early
    ]
    flags = stuck_flags(rows)
    assert {(f["clip_id"], f["platform"]) for f in flags} == {("c1", "x"), ("c2", "youtube")}
    assert len(rows) == 5  # input untouched; flags only


class _ScoutSB:
    def __init__(self):
        self.t = {
            "pods": [{"id": "p1", "slug": "pod-1"}, {"id": "p2", "slug": "pod-2"}],
            "streamers": [{"slug": "lacy", "pod_id": "p1"}, {"slug": "xqc", "pod_id": "p2"}],
            "campaigns": [{"id": "c1", "streamer_slugs": ["lacy"], "cpm_usd": 2.0, "score": 4.0},
                          {"id": "c2", "streamer_slugs": ["lacy"], "cpm_usd": 1.0, "score": 4.0},
                          {"id": "c3", "streamer_slugs": ["xqc", "lacy"], "cpm_usd": 3.0, "score": 4.0}],
            "pod_campaigns": [{"pod_id": "p1", "campaign_id": "c3", "status": "joined", "scout": {}}],
        }
        self.writes = []

    def active_campaigns(self):
        return self.t["campaigns"]

    def select(self, table, **p):
        rows = self.t[table]
        if "pod_id" in p:
            rows = [r for r in rows if r["pod_id"] == p["pod_id"].split(".", 1)[1]]
        return rows

    def insert(self, table, rows, **kw):
        self.writes += rows
        return rows


def test_scout_pods_suggests_and_keeps_zo_calls():
    sb = _ScoutSB()
    assert scout_pods(sb) == 2
    got = {(w["pod_id"], w["campaign_id"]) for w in sb.writes}
    assert got == {("p1", "c1"), ("p2", "c3")}          # c2 at $1 fails D072; p1/c3 is joined
    assert all(w["status"] == "suggested" for w in sb.writes)
    assert sb.writes[0]["scout"]["verdict"] == "pursue"


def test_pipeline_pod_fields(tmp_path):
    from clipworker.pipeline import Pipeline
    from clipworker.store import Store
    ch = [{"platform": "twitch", "login": "lacy"}]
    off = Pipeline(parse_settings({"channels": ch}, tmp_path), Store(":memory:"), None,
                   supabase=_SB([{"id": "u1", "slug": "pod-1"}]))
    assert off._pod_fields("twitch:lacy") == {}
    sb = _SB([{"id": "u1", "slug": "pod-1"}])
    on = Pipeline(parse_settings({"channels": ch, "pods": {"enabled": True}}, tmp_path), Store(":memory:"),
                  None, supabase=sb)
    assert on._pod_fields("twitch:lacy") == {"pod_id": "u1"}
    assert on._pod_fields("twitch:lacy") == {"pod_id": "u1"} and sb.calls == 1   # resolved once
    bad = Pipeline(parse_settings({"channels": ch, "pods": {"enabled": True}}, tmp_path), Store(":memory:"),
                   None, supabase=_SB(boom=True))
    assert bad._pod_fields("twitch:lacy") == {}
