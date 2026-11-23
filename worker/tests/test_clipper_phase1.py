"""Clipper wiring Phase 1 (D089): brain, chat mood/lift, viewer clips, CLIP THAT, dry run."""
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from clipworker import brain
from clipworker.config import DEFAULT_REACTIONS, Channel, DetectorParams, Features, Settings
from clipworker.detector.signals import lift_weight, mood_hits
from clipworker.detector.spike import SpikeDetector
from clipworker.dryrun import render_report, run_dry
from clipworker.ingest import viewer_clips as vc
from clipworker.judge.grok import validate
from clipworker.live import LiveRunner
from clipworker.pipeline import Pipeline
from clipworker.remote.rights import RightsGate
from clipworker.store import Store
from clipworker.transcribe import Word

from fakes import FakeSupabase

P = DetectorParams()


# --- brain -----------------------------------------------------------------------------
def test_brain_roundtrip_versions_and_md(tmp_path):
    b = brain.load(tmp_path, "lacy")
    assert b.learning and b.version == 0 and brain.apply(b, P) == P
    for _ in range(6):
        b = brain.update(b, [], P)
        brain.save(b, tmp_path)
    assert brain.load(tmp_path, "lacy").version == 6
    assert sorted(p.name for p in (tmp_path / "versions").iterdir()) == [
        f"brain-v{i}.json" for i in (3, 4, 5, 6)]
    assert "learning" in (tmp_path / "brain.md").read_text(encoding="utf-8")


def test_template_brain_json_loads(tmp_path):
    (tmp_path / "brain.json").write_text('{"version":0,"weights":{},"bias":null,"baseline":{},'
                                         '"chat_word_lift":{},"counts":{"streams_watched":0,'
                                         '"positives":0,"negatives":0},"updated":null}', encoding="utf-8")
    assert brain.load(tmp_path, "lacy").counts["positives"] == 0


def test_brain_cold_start_then_applies():
    b = brain.Brain("lacy", weights={"z_chat": 0.3, "z_audio": 0.35})
    assert b.learning and brain.apply(b, P) == P            # 0 streams watched
    for _ in range(3):
        b = brain.note_stream(b)
    p = brain.apply(b, P)
    assert not b.learning and p.w_chat == 0.3 and p.w_audio == 0.35 and p.w_unique == P.w_unique


def test_refit_moves_toward_signal_capped_and_rescaled():
    b = brain.Brain("lacy", counts={"streams_watched": 5})
    pos = [({"z_chat": 2, "z_audio": 6}, 1.0)] * 20      # good clips were loud
    neg = [({"z_chat": 6, "z_audio": 0}, -1.0)] * 20     # chat-only spikes got rejected
    w = brain.refit(b, pos + neg, P)
    cur = brain.current_weights(b, P)
    assert w["z_audio"] > cur["z_audio"] and w["z_chat"] < cur["z_chat"]
    assert abs(sum(w.values()) - sum(cur.values())) < 1e-3
    assert w["z_chat"] >= cur["z_chat"] * 0.75 * 0.9         # capped step (before rescale)
    assert brain.refit(b, pos, P) == cur                       # one class only: no change


def test_update_counts_and_cold_start_keeps_weights():
    b = brain.Brain("lacy")
    nb = brain.update(b, [({"z_chat": 1}, 1.0), ({"z_chat": 2}, -0.2)], P, lift={"LACYW": 4.0})
    assert nb.counts["positives"] == 1 and nb.counts["negatives"] == 1
    assert nb.weights == {} and nb.chat_word_lift == {"LACYW": 4.0} and nb.version == 1


def test_chat_word_lift():
    pos = ["LACYW LACYW"] * 6 + ["KEKW"] * 6
    base = ["KEKW"] * 50 + ["hello"] * 50
    lift = brain.chat_word_lift(pos, base, everywhere={"KEKW"})
    assert "LACYW" in lift and "KEKW" not in lift and "HELLO" not in lift


def test_labels_from_clips():
    rows = brain.labels_from_clips([{"id": "c1", "job_id": "j1", "state": "published", "revision": 1},
                                    {"id": "c2", "job_id": "j2", "state": "rejected"},
                                    {"id": "c3", "job_id": "j3", "state": "pending_review"}], "lacy")
    assert [(r["signal"], r["weight"]) for r in rows] == [("approved_revised", 0.7), ("rejected", -1.0)]


# --- chat mood + lift ------------------------------------------------------------------
def test_mood_and_lift_tokens():
    assert mood_hits("KEKW KEKW") == 1 and mood_hits("NO WAY 😂") == 2 and mood_hits("WHAT?? LMAO") == 2
    assert mood_hits("hello there") == 0
    assert lift_weight("lacyW lacyW", {"LACYW": 4.0}) == 4.0 and lift_weight("x", {}) == 0.0


def test_detector_mood_term_off_by_default():
    def run(params, lift=None):
        d = SpikeDetector("c", params, DEFAULT_REACTIONS, lift=lift)
        d.keep_ticks = True
        for t in range(0, 200):
            d.add_message(t, f"u{t % 5}", "hello")
            d.tick(float(t))
        for i in range(30):
            d.add_message(200 + i * 0.1, f"x{i}", "LACYW KEKW")
        d.tick(203.0)
        return d.ticks[-1]
    off = run(P)
    on = run(replace(P, w_mood=0.3, w_lift=0.3), lift={"LACYW": 5.0})
    assert off.mood > 0 and on.score > off.score and on.lift > 0 and off.lift == 0


# --- viewer clips ----------------------------------------------------------------------
CLIPS = {"data": [{"id": "A", "created_at": "2026-11-22T20:00:30Z", "duration": 30, "view_count": 80,
                   "creator_id": "123"},
                  {"id": "B", "created_at": "2026-11-22T20:30:00Z", "duration": 20, "view_count": 5,
                   "creator_id": "9"}]}


def test_parse_and_match_viewer_clips():
    clips = vc.parse_clips(CLIPS)
    a = clips[0]
    assert a.moment_ts == vc._epoch("2026-11-22T20:00:15Z") and len(a.creator_hash) == 16
    assert "123" not in a.creator_hash
    by_job, rows = vc.label_rows(clips, {"j1": a.moment_ts + 10, "j2": a.moment_ts + 60}, "lacy")
    assert by_job == {"j1": ["A"]}
    assert [r["job_id"] for r in rows] == ["j1", "viewer:B"] and rows[1]["reason"].startswith("missed")


def _settings(tmp_path, **flags):
    ch = Channel("twitch:lacy", "twitch", "lacy", "lacy", None, DEFAULT_REACTIONS, P)
    return Settings(work_dir=tmp_path, channels=[ch], caption_style=None, features=Features(**flags))


def test_live_viewer_clip_poll_badges_job(tmp_path):
    s, sb, store = _settings(tmp_path, viewer_clips=True), FakeSupabase(), Store(":memory:")
    pipe = Pipeline(s, store, RightsGate(lambda: [], roster={"lacy"}), None, None, None)
    run = LiveRunner(s, store, pipe, None, None)
    run.sb, run.live = sb, {"twitch:lacy"}
    run.stream_info = {"twitch:lacy": {"user_id": "42"}}
    clip = vc.parse_clips(CLIPS)[0]
    store.create_job("j1", "twitch:lacy", clip.moment_ts - 25, clip.moment_ts + 15, clip.moment_ts + 5,
                     3.0, {"features": {}}, "k1")
    got = []
    n = run.poll_viewer_clips_once(clip.created_ts + 60, fetch=lambda b, s_, e: got.append(b) or [clip])
    assert n == 1 and got == ["42"] and store.job("j1").data["badges"] == ["viewers_clipped"]
    assert sb.t["clip_labels"][0]["signal"] == "viewer_clip"
    assert run.poll_viewer_clips_once(clip.created_ts + 120, fetch=lambda *a: [clip]) == 0   # seen once


# --- CLIP THAT + dry run ---------------------------------------------------------------
class DropJudge:
    def cost_usd(self, u):
        return 0.0

    def judge(self, words, chat, scores, rules, dur, min_len, max_len):
        raw = {"keep": False, "category": "other", "hook_type": "none", "standalone": False, "score_10": 2,
               "trim_in": 5, "trim_out": 30, "hook": "h", "title": "t", "post_caption": "", "hashtags": [],
               "emphasis_words": [], "confidence": 0.3, "reason": "meh"}
        return validate(raw, dur, min_len, max_len, words)


def test_clip_that_is_kept_and_labelled(tmp_path):
    s, sb, store = _settings(tmp_path, clip_that=True), FakeSupabase(), Store(":memory:")
    pipe = Pipeline(s, store, RightsGate(lambda: [], roster={"lacy"}), None, DropJudge(), sb)
    jid = pipe.clip_that("twitch:lacy", 5000.0)
    job = store.job(jid)
    assert (job.start_ts, job.end_ts) == (4960.0, 5000.0) and job.data["force_keep"]
    assert sb.t["clip_labels"][0]["signal"] == "missed_moment"
    store.advance(jid, "captured", {"capture": {"video": "v", "audio": "a", "start_ts": 4960, "end_ts": 5000}})
    store.advance(jid, "transcribed", {"words": [], "transcript": ""})
    pipe._judge(store.job(jid))
    assert store.job(jid).stage == "judged" and "CLIP THAT" in store.job(jid).data["judgment"]["reason"]


def test_clip_requests_only_for_live_channels(tmp_path):
    s, sb, store = _settings(tmp_path, clip_that=True), FakeSupabase(), Store(":memory:")
    sb.insert("clip_requests", {"id": "r1", "streamer": "lacy", "status": "open", "seconds": 40,
                                "source": "dashboard", "requested_at": "2026-11-22T20:00:00Z"})
    pipe = Pipeline(s, store, RightsGate(lambda: [], roster={"lacy"}), None, DropJudge(), sb)
    assert pipe.take_clip_requests(5000.0, live=set()) == 1
    assert sb.t["clip_requests"][0]["status"] == "failed"


def _chat_file(tmp_path):
    comments = [{"content_offset_seconds": t, "commenter": {"name": f"u{t % 9}"}, "message": {"body": "hi"}}
                for t in range(0, 600)]
    comments += [{"content_offset_seconds": 400 + i * 0.05, "commenter": {"name": f"x{i}"},
                  "message": {"body": "KEKW NO WAY"}} for i in range(250)]
    f = tmp_path / "chat.json"
    f.write_text(json.dumps({"comments": comments}), encoding="utf-8")
    return f


def test_run_dry_end_to_end_nothing_uploaded(tmp_path):
    s = _settings(tmp_path, score_100=True)
    words = [Word(18 + i * 0.4, 18.3 + i * 0.4, w) for i, w in enumerate("no way he did that KEKW".split())]

    class Tr:
        def transcribe(self, wav):
            return words

    class Judge:
        def cost_usd(self, u):
            return 0.0

        def judge(self, w, chat, scores, rules, dur, min_len, max_len):
            raw = {"keep": True, "category": "funny", "hook_type": "reaction_peak", "standalone": True,
                   "score_10": 8, "trim_in": 18, "trim_out": 34, "hook": "no way", "title": "Lacy can't believe it",
                   "post_caption": "", "hashtags": [], "emphasis_words": ["WAY"], "confidence": 0.9,
                   "reason": "r", "parts": {"hook": 9, "payoff": 9, "standalone": 8, "emotion": 9, "share": 8},
                   "send_test": "group chat: LMAO", "why": "w", "proof_frame_ts": 20}
            return validate(raw, dur, min_len, max_len, w)

    def extract(_b, start, end, out_dir):
        out_dir.mkdir(parents=True, exist_ok=True)
        return {"video": str(out_dir / "w.mp4"), "audio": str(out_dir / "w.wav"), "start_ts": start,
                "end_ts": end, "partial": False}

    def render(job_id, video, job_dir, t_in, t_out, *a, **k):
        return {"video": str(job_dir / "clip.mp4"), "thumbnail": "t.jpg", "duration": t_out - t_in}

    qa = lambda *a, **k: SimpleNamespace(passed=True, failures=[], metrics={"lufs": -14})
    out = run_dry(s, "twitch:lacy", Path("vod.mp4"), _chat_file(tmp_path), tmp_path / "dry", Tr(), Judge(),
                  loudness=[], extract=extract, render=render, qa=qa)
    rep = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert rep["flags"]["dry_run"] and rep["judged"] >= 1
    row = rep["jobs"][0]
    assert row["stage"] == "qa_passed" and row["score"] >= 60 and row["title"] == "Lacy can't believe it"
    assert list(out.glob("renders/*/dryrun.json"))
    assert "would reach review 1" in (out / "report.md").read_text(encoding="utf-8")


def test_run_dry_review_mode_uploads_pending_review(tmp_path):
    s = _settings(tmp_path, score_100=True)

    class Tr:
        def transcribe(self, wav):
            return [Word(18 + i * 0.4, 18.3 + i * 0.4, w) for i, w in enumerate("no way he did that".split())]

    class SB:
        def __init__(self):
            self.inserts, self.uploads = [], []

        def upload(self, path, file, ct):
            self.uploads.append(path)
            return path

        def insert(self, table, row, **k):
            self.inserts.append((table, row))
            return [row]

        def select(self, table, **k):
            return [{"id": "s1"}] if table == "streamers" else []

        def log_candidate(self, row):
            pass

        def log_spend(self, *a, **k):
            pass

    def extract(_b, start, end, out_dir):
        out_dir.mkdir(parents=True, exist_ok=True)
        return {"video": str(out_dir / "w.mp4"), "audio": str(out_dir / "w.wav"), "start_ts": start,
                "end_ts": end, "partial": False}

    def render(job_id, video, job_dir, t_in, t_out, *a, **k):
        job_dir.mkdir(parents=True, exist_ok=True)
        (job_dir / "clip.mp4").write_bytes(b"x")
        (job_dir / "t.jpg").write_bytes(b"x")
        return {"video": str(job_dir / "clip.mp4"), "thumbnail": str(job_dir / "t.jpg"), "duration": t_out - t_in}

    from clipworker.judge.heuristic import HeuristicJudge
    sb = SB()
    qa = lambda *a, **k: SimpleNamespace(passed=True, failures=[], metrics={"lufs": -14})
    out = run_dry(s, "twitch:lacy", Path("vod.mp4"), _chat_file(tmp_path), tmp_path / "dry", Tr(),
                  HeuristicJudge(), loudness=[], extract=extract, render=render, qa=qa,
                  supabase=sb, vod_started_at=1_700_000_000)
    rep = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert not rep["flags"]["dry_run"]
    clips = [r for t, r in sb.inserts if t == "clips"]
    assert clips and all(c["state"] == "pending_review" for c in clips)
    assert clips[0]["moment_at"].startswith("2023-")
    assert rep["jobs"][0]["stage"] == "uploaded"
    assert not any(t == "publications" for t, _ in sb.inserts)


def test_render_report_lists_gated():
    md = render_report({"channel": "twitch:lacy", "vod": "v", "flags": {"dead_air_gate": True},
                        "candidates": 2, "judged": 0, "jobs": [],
                        "gated": [{"start": 65, "reason": "dead air: before show_start"}]})
    assert "0:01:05 | gated" in md and "dead_air_gate" in md


def test_rejudge_updates_metadata_never_state(tmp_path):
    from clipworker.judge.grok import Judgment
    from clipworker.rejudge import rejudge_queue
    from clipworker.store import Store
    s = _settings(tmp_path, score_100=False)
    live = tmp_path / "live.sqlite3"
    st = Store(live)
    jid = "j1"
    st.create_job(jid, "twitch:lacy", 10.0, 50.0, 30.0, 5.0, {
        "capture": {"start_ts": 10.0, "end_ts": 50.0}, "rules": {"min_s": 10, "max_s": 60},
        "words": [], "features": {"z_chat": 2.0}, "chat_sample": [], "rules_summary": "", "peak_ts": 30.0}, None)
    st.db.commit()

    class SB:
        updates = []

        def select(self, table, **k):
            return [{"id": "c1", "job_id": jid, "channel_key": "twitch:lacy", "title": "UNJUDGED: x", "judge": {}}]

        def update(self, table, match, values):
            self.updates.append((table, match, values))

        def log_spend(self, *a, **k):
            pass

    class J:
        def judge(self, *a, **k):
            return Judgment(False, "funny", 1, 20, "h", "Boring bit", [], 0.4, "meh", score_10=3)

    sb = SB()
    rows = rejudge_queue(s, live, tmp_path / "rj", sb, J())
    assert rows[0]["keep"] is False
    (_, match, vals), = sb.updates
    assert match == {"id": "c1"} and "state" not in vals and vals["title"] == "WEAK: Boring bit"
