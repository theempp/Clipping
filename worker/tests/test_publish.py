import json
from pathlib import Path

import httpx
import pytest

from clipworker.publish.base import PostResult, PublishError
from clipworker.publish.oauth import TokenSource
from clipworker.publish.runner import PublishRunner, pick_destinations
from clipworker.publish.x import XPublisher
from clipworker.publish.youtube import YouTubePublisher
from clipworker.store import Store

from fakes import FakeSupabase


class FakePub:
    platform = "youtube"

    def __init__(self, fail=None):
        self.calls, self.fail = [], fail

    def post(self, video, title, description, tags):
        self.calls.append(title)
        if self.fail:
            raise self.fail
        return PostResult(f"id{len(self.calls)}", f"https://example.test/{len(self.calls)}")


def _setup(tmp_path, state="approved", daily_cap=10):
    sb = FakeSupabase()
    sb.insert("destinations", [{"id": "d-yt", "platform": "youtube", "label": "main",
                                "credential_ref": "YT_MAIN", "streamer_id": None, "daily_cap": daily_cap},
                               {"id": "d-x", "platform": "x", "label": "main", "credential_ref": "X_MAIN",
                                "streamer_id": None, "daily_cap": daily_cap}])
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"v")
    sb.insert("clips", {"id": "c1", "job_id": "j1", "state": state, "title": "t",
                        "manifest": {"video": str(video), "tags": ["#lacy"]}})
    return sb


def test_pick_destinations_follows_posted_platforms():
    ds = [{"id": "yt", "platform": "youtube", "streamer_id": None}, {"id": "x", "platform": "x", "streamer_id": None}]
    assert {d["id"] for d in pick_destinations({"post_platforms": ["x"]}, ds, [])} == {"x"}
    assert pick_destinations({"post_platforms": []}, ds, []) == []
    assert {d["id"] for d in pick_destinations({}, ds, [])} == {"yt", "x"}


def test_pick_destinations_prefers_dedicated():
    ds = [{"id": "shared", "platform": "youtube", "streamer_id": None},
          {"id": "lacy", "platform": "youtube", "streamer_id": "s-lacy"},
          {"id": "clix", "platform": "youtube", "streamer_id": "s-clix"},
          {"id": "x", "platform": "x", "streamer_id": None}]
    got = {d["id"] for d in pick_destinations({"streamer_id": "s-lacy"}, ds, [])}
    assert got == {"lacy", "x"}
    got = {d["id"] for d in pick_destinations({"streamer_id": "s-lacy"}, ds, ["youtube"])}
    assert got == {"lacy"}


def test_only_approved_clips_publish_and_never_twice(tmp_path):
    sb = _setup(tmp_path, state="pending_review")
    yt, x = FakePub(), FakePub()
    r = PublishRunner(sb, {"YT_MAIN": yt, "X_MAIN": x}, lambda c: c["manifest"]["video"])
    assert r.run_once() == [] and yt.calls == []           # not approved -> untouched
    sb.human("c1", "approved")
    assert r.run_once() == ["c1: published"]
    assert len(yt.calls) == len(x.calls) == 1
    assert {p["status"] for p in sb.t["publications"]} == {"posted"}
    assert r.run_once() == [] and len(yt.calls) == 1        # published clip never re-posted
    states = [e["to"] for e in sb.t["clip_events"]]
    assert states == ["scheduled", "published"]


def test_partial_failure_retries_only_failed_platform(tmp_path):
    sb = _setup(tmp_path)
    yt, x = FakePub(), FakePub(fail=PublishError("x 503", retryable=True))
    t = [0.0]
    r = PublishRunner(sb, {"YT_MAIN": yt, "X_MAIN": x}, lambda c: c["manifest"]["video"],
                      clock=lambda: t[0])
    assert r.run_once()[0].startswith("c1: failed")
    x.fail = None
    assert r.run_once() == []                     # backoff: no instant retry
    t[0] = 301
    assert r.run_once() == ["c1: published"]
    assert len(yt.calls) == 1 and len(x.calls) == 2


def test_non_retryable_failure_stays_failed(tmp_path):
    sb = _setup(tmp_path)
    x = FakePub(fail=PublishError("x 403 forbidden"))
    t = [0.0]
    r = PublishRunner(sb, {"YT_MAIN": FakePub(), "X_MAIN": x}, lambda c: c["manifest"]["video"],
                      clock=lambda: t[0])
    r.run_once()
    x.fail = None
    t[0] = 10_000
    assert r.run_once() == [] and len(x.calls) == 1


def test_interrupted_post_is_not_auto_retried(tmp_path):
    sb = _setup(tmp_path)
    sb.insert("publications", {"clip_id": "c1", "destination_id": "d-x", "status": "posting",
                               "attempts": 1})
    yt, x = FakePub(), FakePub()
    r = PublishRunner(sb, {"YT_MAIN": yt, "X_MAIN": x}, lambda c: c["manifest"]["video"])
    out = r.run_once()
    assert "outcome unknown" in out[0] and x.calls == [] and len(yt.calls) == 1


def test_daily_cap(tmp_path):
    sb = _setup(tmp_path, daily_cap=1)
    import datetime as dt
    sb.insert("publications", {"clip_id": "old", "destination_id": "d-yt", "status": "posted",
                               "posted_at": dt.datetime.now(dt.timezone.utc).isoformat()})
    yt = FakePub()
    r = PublishRunner(sb, {"YT_MAIN": yt, "X_MAIN": FakePub()}, lambda c: c["manifest"]["video"])
    assert "daily cap" in r.run_once()[0] and yt.calls == []


def test_missing_credentials_fail_loudly(tmp_path):
    sb = _setup(tmp_path)
    r = PublishRunner(sb, {}, lambda c: c["manifest"]["video"])
    assert "no credentials" in r.run_once()[0]


def test_oauth_rotation_persisted(monkeypatch):
    monkeypatch.setenv("X_T_CLIENT_ID", "cid")
    monkeypatch.setenv("X_T_CLIENT_SECRET", "sec")
    monkeypatch.setenv("X_T_REFRESH_TOKEN", "r0")
    seen = []

    def handler(req):
        body = dict(x.split("=") for x in req.content.decode().split("&"))
        seen.append(body["refresh_token"])
        return httpx.Response(200, json={"access_token": f"a{len(seen)}", "refresh_token": f"r{len(seen)}",
                                         "expires_in": 0})
    store = Store(":memory:")
    ts = TokenSource("https://api.x.com/2/oauth2/token", "X_T", store.kv_get, store.kv_set,
                     httpx.Client(transport=httpx.MockTransport(handler)), basic_auth=True)
    assert ts.access_token() == "a1"
    assert ts.access_token() == "a2"          # expired -> refresh with the rotated token
    assert seen == ["r0", "r1"] and store.kv_get("oauth:X_T:refresh") == "r2"


class StaticTokens:
    def access_token(self):
        return "tok"


def test_youtube_resumable_upload(tmp_path):
    v = tmp_path / "c.mp4"
    v.write_bytes(b"0123456789")

    def handler(req):
        if req.method == "POST":
            meta = json.loads(req.content)
            assert meta["status"]["selfDeclaredMadeForKids"] is False
            assert req.headers["X-Upload-Content-Length"] == "10"
            return httpx.Response(200, headers={"Location": "https://upload.test/session1"})
        assert str(req.url) == "https://upload.test/session1" and req.content == b"0123456789"
        return httpx.Response(200, json={"id": "abc"})
    res = YouTubePublisher(StaticTokens(), httpx.Client(transport=httpx.MockTransport(handler))).post(
        v, "title", "desc", ["#lacy"])
    assert res.url == "https://youtube.com/shorts/abc"


def test_x_chunked_upload_then_post(tmp_path):
    v = tmp_path / "c.mp4"
    v.write_bytes(b"x" * (4 * 1024 * 1024 + 5))
    log = []

    def handler(req):
        p = req.url.path
        log.append(p)
        if p.endswith("/initialize"):
            return httpx.Response(200, json={"data": {"id": "m1"}})
        if p.endswith("/append"):
            return httpx.Response(204)
        if p.endswith("/finalize"):
            return httpx.Response(200, json={"data": {"id": "m1", "processing_info":
                                                      {"state": "pending", "check_after_secs": 1}}})
        if p == "/2/media/upload":
            return httpx.Response(200, json={"data": {"processing_info": {"state": "succeeded"}}})
        if p == "/2/tweets":
            body = json.loads(req.content)
            assert body["media"]["media_ids"] == ["m1"] and "#lacy" in body["text"]
            assert "http" not in body["text"]                     # no URL = cheaper post
            return httpx.Response(201, json={"data": {"id": "t9"}})
        return httpx.Response(404)
    res = XPublisher(StaticTokens(), httpx.Client(transport=httpx.MockTransport(handler)),
                     sleep=lambda s: None).post(v, "No way", "", ["lacy"])
    assert res.url == "https://x.com/i/status/t9" and res.cost_usd > 0
    assert log.count("/2/media/upload/m1/append") == 2
