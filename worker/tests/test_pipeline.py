import shutil
from pathlib import Path

from clipworker.config import DEFAULT_REACTIONS, Channel, DetectorParams, Settings
from clipworker.detector.spike import Moment
from clipworker.judge.grok import Judgment
from clipworker.pipeline import Pipeline
from clipworker.remote.rights import RightsGate
from clipworker.store import Store
from clipworker.transcribe import Word

from conftest import TEST_LAYOUT, TEST_STYLE, needs_ffmpeg
from fakes import FakeSupabase

WORDS = [Word(5 + i * 0.5, 5.4 + i * 0.5, w) for i, w in
         enumerate("bro no way he just hit that from across the map".split())]


class FakeTr:
    def __init__(self, words=WORDS):
        self.words, self.n = words, 0

    def transcribe(self, wav):
        self.n += 1
        return self.words


class FakeJudge:
    def __init__(self, keep=True):
        self.keep, self.n = keep, 0

    def cost_usd(self, usage):
        return 0.001

    def judge(self, words, chat, scores, rules, dur, min_len, max_len):
        self.n += 1
        assert len(chat) <= 30 and dur > 0
        return Judgment(self.keep, "clutch", 2.0, 16.0, "he hit THAT", "No way he hit that",
                        ["that"], 0.9, "payoff", usage={"total_tokens": 900})


def _env(tmp_path, source_video, keep=True, active=True, channels=("twitch:lacy",)):
    sb = FakeSupabase()
    sb.insert("streamers", {"id": "s-lacy", "slug": "lacy"})
    sb.insert("streamers", {"id": "s-clix", "slug": "clix"})
    sb.insert("campaigns", {"id": "camp1", "title": "Lacy Nov", "status": "active" if active else "draft",
                            "streamer_slugs": ["lacy", "clix"], "platforms": ["youtube", "x"], "score": 4,
                            "rules": {"min_s": 10, "max_s": 60, "required_tags": ["#lacy"]}})
    chans = [Channel(k, "twitch", k.split(":")[1], k.split(":")[1], TEST_LAYOUT, DEFAULT_REACTIONS,
                     DetectorParams()) for k in channels]
    s = Settings(work_dir=tmp_path, channels=chans, caption_style=TEST_STYLE)
    store = Store(":memory:")

    def fake_extract(buf, start, end, out_dir):
        out_dir.mkdir(parents=True, exist_ok=True)
        v = out_dir / "window.mp4"
        shutil.copy(source_video, v)
        return {"video": str(v), "audio": str(v), "start_ts": start, "end_ts": start + 30, "partial": False}

    pipe = Pipeline(s, store, RightsGate(sb.active_campaigns), FakeTr(), FakeJudge(keep), sb,
                    clock=lambda: 10_000.0, extract=fake_extract)
    return pipe, sb, store


def _moment(key="twitch:lacy", t=1000.0):
    return Moment(key, t, t + 3, 4.2, t + 5, t - 25, t + 15, {"rate": 6.0, "z_chat": 8.0})


@needs_ffmpeg
def test_moment_to_pending_review(tmp_path, source_video):
    pipe, sb, store = _env(tmp_path, source_video)
    store.add_messages([("twitch:lacy", 998.0 + i * 0.1, f"u{i}", "KEKW") for i in range(50)])
    job = pipe.on_moment(_moment())
    assert job and pipe.on_moment(_moment(t=1004.0)) is None      # dedupe same 10 s bucket
    for _ in range(8):
        pipe.run_once()
    j = store.job(job)
    assert j.stage == "uploaded", (j.stage, j.last_error, j.data.get("qa"))
    clip = sb.t["clips"][0]
    assert clip["state"] == "pending_review" and clip["campaign_id"] == "camp1"
    assert clip["streamer_id"] == "s-lacy" and "#lacy" in clip["description"]
    assert set(sb.uploads) == {f"lacy/{job}/clip.mp4", f"lacy/{job}/thumb.jpg"}
    assert sb.t["spend"][0]["kind"] == "grok"
    assert sb.t["candidate_log"][0]["outcome"] == "kept"


def test_rights_gate_blocks_without_active_campaign(tmp_path):
    pipe, sb, store = _env(tmp_path, Path("unused"), active=False)
    assert pipe.on_moment(_moment()) is None
    assert list(store.jobs_in("detected")) == []


def test_capture_waits_for_buffer(tmp_path):
    pipe, sb, store = _env(tmp_path, Path("unused"))
    pipe.clock = lambda: 1005.0          # window end 1015 not yet buffered
    job = pipe.on_moment(_moment())
    pipe.run_once()
    assert store.job(job).stage == "detected"


@needs_ffmpeg
def test_judge_drop_is_logged(tmp_path, source_video):
    pipe, sb, store = _env(tmp_path, source_video, keep=False)
    job = pipe.on_moment(_moment())
    for _ in range(4):
        pipe.run_once()
    assert store.job(job).stage == "dropped"
    assert sb.t["candidate_log"][0]["outcome"] == "dropped" and sb.t["clips"] == []


@needs_ffmpeg
def test_squad_duplicate_dropped(tmp_path, source_video):
    pipe, sb, store = _env(tmp_path, source_video, channels=("twitch:lacy", "twitch:clix"))
    a = pipe.on_moment(_moment("twitch:lacy", 1000.0))
    b = pipe.on_moment(_moment("twitch:clix", 1008.0))
    for _ in range(8):
        pipe.run_once()
    stages = {store.job(a).stage, store.job(b).stage}
    assert stages == {"uploaded", "dropped"}
    assert len(sb.t["clips"]) == 1
    assert any(r["outcome"] == "duplicate" for r in sb.t["candidate_log"])


def test_failing_step_parks_job_after_retries(tmp_path):
    pipe, sb, store = _env(tmp_path, Path("unused"))

    def boom(*a, **k):
        raise RuntimeError("buffer gone")
    pipe._extract = boom
    job = pipe.on_moment(_moment())
    for _ in range(3):
        pipe.run_once()
    j = store.job(job)
    assert j.stage == "error" and j.attempts == 3
    assert sb.t["candidate_log"][-1]["outcome"] == "error"


@needs_ffmpeg
def test_revision_rerenders_and_returns_to_review(tmp_path, source_video):
    pipe, sb, store = _env(tmp_path, source_video)
    job = pipe.on_moment(_moment())
    for _ in range(8):
        pipe.run_once()
    clip = sb.t["clips"][0]
    sb.human(clip["id"], "revise")
    sb.insert("revisions", {"clip_id": clip["id"], "kind": "trim", "note": "start later",
                            "payload": {"trim_in": 4.0, "trim_out": 20.0}, "resolved_at": None})
    sb.insert("revisions", {"clip_id": clip["id"], "kind": "title", "note": "better title",
                            "payload": {"title": "He hit THAT from spawn"}, "resolved_at": None})
    assert pipe.process_revisions() == 1
    clip = sb.t["clips"][0]
    assert clip["state"] == "pending_review" and clip["revision"] == 1
    assert clip["title"] == "He hit THAT from spawn"
    assert abs(clip["duration_s"] - 16.0) < 0.01
    assert all(r["resolved_at"] for r in sb.t["revisions"])
    assert pipe.transcriber.n == 1 and pipe.judge.n == 1      # only render+QA re-ran
