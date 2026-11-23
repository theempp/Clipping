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

    def parse_edit(self, note):
        self.notes = getattr(self, "notes", []) + [note]
        return {"max_len_s": 8.0, "sfx": False, "caption_colour": "#2F80FF"}, {"total_tokens": 50}


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
    assert set(sb.uploads) == {f"lacy/{job}/clip.mp4", f"lacy/{job}/thumb.jpg", f"lacy/{job}/source.mp4"}
    assert clip["source_path"] == f"lacy/{job}/source.mp4"   # before/after on the dashboard
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


@needs_ffmpeg
def test_revision_failing_qa_is_flagged_not_retried(tmp_path, source_video):
    pipe, sb, store = _env(tmp_path, source_video)
    pipe.on_moment(_moment())
    for _ in range(8):
        pipe.run_once()
    clip = sb.t["clips"][0]
    sb.human(clip["id"], "revise")
    sb.insert("revisions", {"clip_id": clip["id"], "kind": "trim", "note": "way too short",
                            "payload": {"trim_in": 4.0, "trim_out": 4.5}, "resolved_at": None})
    assert pipe.process_revisions() == 0
    clip = sb.t["clips"][0]
    assert clip["state"] == "revise"
    f = clip["revise_failed"]
    assert f["rev"] == 1 and f["reason"] and f["revisions"] == [sb.t["revisions"][0]["id"]]
    renders = pipe.process_revisions()  # same notes: not re-rendered again
    assert renders == 0 and sb.t["clips"][0]["revise_failed"] == f


@needs_ffmpeg
def test_revision_box_plain_english(tmp_path, source_video):
    pipe, sb, store = _env(tmp_path, source_video)
    pipe.on_moment(_moment())
    for _ in range(8):
        pipe.run_once()
    clip = sb.t["clips"][0]
    sb.human(clip["id"], "revise")
    sb.insert("revisions", {"clip_id": clip["id"], "kind": "other", "resolved_at": None, "payload": {},
                            "note": "under 30 seconds, no sound effects, blue captions"})
    assert pipe.process_revisions() == 1
    clip = sb.t["clips"][0]
    assert pipe.judge.notes == ["under 30 seconds, no sound effects, blue captions"]
    # asked for 8 s, campaign minimum is 10 s: clamps to 10
    assert abs(clip["duration_s"] - 10.0) < 0.01 and clip["manifest"]["sfx"] is False
    ass = (Path(clip["manifest"]["video"]).parent / "captions.ass").read_text(encoding="utf-8")
    assert "&H00FF802F" in ass                       # #2F80FF as ASS BGR highlight
    # the note's style asks became standing rules (D078); the title-free note gives three
    assert {r["key"] for r in sb.t["edit_rules"]} == {"max_len_s", "sfx", "caption_colour"}
    assert sb.t["revisions"][0]["learned_at"]


def test_revision_note_fixes_clips_already_waiting(tmp_path, source_video):
    """Zo's zoom note on clip A re-edits clip B, already in review with the old zooms (D078)."""
    pipe, sb, store = _env(tmp_path, source_video)
    pipe.on_moment(_moment())
    pipe.on_moment(_moment(t=1060.0))
    for _ in range(16):
        pipe.run_once()
    a, b = sb.t["clips"][:2]
    for c in (a, b):  # rendered before D077: zooms present, old motion
        sb.update("clips", {"id": c["id"]}, {"manifest": {**c["manifest"], "zooms": [2.0], "motion": {}}})
    sb.human(a["id"], "revise")
    sb.insert("revisions", {"clip_id": a["id"], "kind": "other", "resolved_at": None, "payload": {},
                            "note": "the zoom in and out is way too sharp, make it smoother"})
    pipe.process_revisions()
    rule = sb.t["edit_rules"][0]
    assert rule["key"] == "zoom_style" and rule["value"] == "smooth"
    b = next(c for c in sb.t["clips"] if c["id"] == b["id"])
    assert b["state"] == "pending_review" and b["revision"] == 1 and not b.get("fixing")
    assert b["manifest"]["motion"]["motion_version"] == 2
    assert sb.t["edit_rules"][0]["fixed_count"] == 1


@needs_ffmpeg
def test_recipe_is_chosen_once_recorded_and_never_zooms(tmp_path, source_video):
    import dataclasses
    import json as _json
    pipe, sb, store = _env(tmp_path, source_video)
    wpath = tmp_path / "weights.json"
    pipe.s = dataclasses.replace(pipe.s, extra={"recipe_weights": str(wpath)})
    job = pipe.on_moment(_moment())
    for _ in range(8):
        pipe.run_once()
    j = store.job(job)
    assert j.stage == "uploaded", (j.stage, j.last_error)
    m = j.data["manifest"]
    rec = m["recipe"]
    assert rec["streamer"] == "twitch:lacy" and m["zooms"] == [] and "zoom" not in rec["tools"]
    assert rec["tools"][:2] == ["hard_cut", "headline_box"] and rec["caption_style"] in ("headline", "headline+words")
    assert j.data["judgment"]["recipe"] == rec
    saved = _json.loads(wpath.read_text())["twitch:lacy"]
    assert saved["clips_made"] == 1 and saved["last_combo"] == rec["tools"]
    # a revision re-renders with the SAME recipe and does not count as a new clip
    clip = sb.t["clips"][0]
    sb.human(clip["id"], "revise")
    sb.insert("revisions", {"clip_id": clip["id"], "kind": "title", "note": "t",
                            "payload": {"title": "New title"}, "resolved_at": None})
    assert pipe.process_revisions() == 1
    assert store.job(job).data["manifest"]["recipe"] == rec
    assert _json.loads(wpath.read_text())["twitch:lacy"]["clips_made"] == 1


@needs_ffmpeg
def test_recipe_off_by_default(tmp_path, source_video):
    pipe, sb, store = _env(tmp_path, source_video)
    job = pipe.on_moment(_moment())
    for _ in range(8):
        pipe.run_once()
    assert "recipe" not in store.job(job).data["manifest"]


@needs_ffmpeg
def test_learning_loop_moves_weights_once_per_clip(tmp_path, source_video):
    import dataclasses
    import json as _json
    pipe, sb, store = _env(tmp_path, source_video)
    wpath = tmp_path / "weights.json"
    pipe.s = dataclasses.replace(pipe.s, extra={"recipe_weights": str(wpath)})
    job = pipe.on_moment(_moment())
    for _ in range(8):
        pipe.run_once()
    clip = sb.t["clips"][0]
    tools = clip["manifest"]["recipe"]["tools"]
    assert pipe.learn_recipes() == 0                       # still pending review: nothing learned
    sb.human(clip["id"], "approved")
    assert pipe.learn_recipes() == 1 and pipe.learn_recipes() == 0   # once only
    sw = _json.loads(wpath.read_text())["twitch:lacy"]
    extras = [t for t in tools if t not in ("hard_cut", "headline_box")]
    assert all(sw["weights"][t] > 1.0 for t in extras)
    assert sb.t["clips"][0]["recipe_learned_at"]
