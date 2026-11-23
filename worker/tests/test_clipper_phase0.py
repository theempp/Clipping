"""Clipper wiring Phase 0 (D089): flags, dead-air gate, 0-100 score, judge schema."""
import json
from pathlib import Path

import httpx
import pytest

from clipworker.config import (DEFAULT_REACTIONS, Channel, ConfigError, DeadAirParams, DetectorParams,
                               Features, Settings, parse_settings)
from clipworker.detector.deadair import (DeadAirGate, dead_air_ratio, frame_reject, parse_frame_log,
                                         words_quiet)
from clipworker.detector.replay import replay
from clipworker.detector.spike import Moment
from clipworker.judge import score as sc
from clipworker.judge.grok import SCHEMA, SCHEMA_100, SYSTEM, SYSTEM_100, GrokJudge, Judgment, validate
from clipworker.pipeline import Pipeline
from clipworker.remote.rights import RightsGate
from clipworker.store import Store
from clipworker.transcribe import Word

from fakes import FakeSupabase

P = DeadAirParams()
RAW = {"keep": True, "category": "funny", "hook_type": "reaction_peak", "standalone": True, "score_10": 8,
       "trim_in": 5, "trim_out": 21, "hook": "he did WHAT", "title": "No way", "post_caption": "no way",
       "hashtags": ["#gta6"], "emphasis_words": ["WHAT"], "confidence": 0.8, "reason": "clear payoff"}
PARTS = {"hook": 9, "payoff": 8, "standalone": 9, "emotion": 8, "share": 8}


# --- flags -----------------------------------------------------------------------------
def test_flags_default_off_and_strict(tmp_path):
    s = parse_settings({"channels": []}, tmp_path)
    assert s.features == Features() and not any(vars(s.features).values())
    s = parse_settings({"channels": [], "features": {"score_100": True}, "dead_air": {"quiet_mult": 0.5}},
                       tmp_path)
    assert s.features.score_100 and not s.features.dead_air_gate and s.dead_air.quiet_mult == 0.5
    with pytest.raises(ConfigError):
        parse_settings({"channels": [], "features": {"autopost": True}}, tmp_path)
    with pytest.raises(ConfigError):
        parse_settings({"channels": [], "features": {"brain": "yes"}}, tmp_path)


def test_channel_agent_and_state_dir(tmp_path):
    s = parse_settings({"channels": [{"platform": "twitch", "login": "Lacy", "agent": "lacy-agent"}]},
                       tmp_path)
    ch = s.channels[0]
    assert ch.agent == "lacy-agent" and s.state_dir(ch) == s.state_root / "lacy"


# --- dead-air gate ---------------------------------------------------------------------
def test_show_start_needs_8_active_seconds_in_30():
    g = DeadAirGate(P)
    for t in range(0, 30, 5):                       # 6 isolated seconds: not a show yet
        g.add_activity(t, True)
    assert g.show_start is None and not g.started(100)
    for t in range(100, 108):
        g.add_activity(t + 0.3, True)
        g.add_activity(t + 0.7, True)               # same second counted once
    assert g.show_start == 100.0 and g.started(100) and not g.started(99)


def test_quiet_multiplier():
    g = DeadAirGate(P)
    g.add_activity(100, True)
    assert g.multiplier(110) == 1.0                 # speech 10 s before the peak
    assert g.multiplier(130) == P.quiet_mult        # nothing within -20/+5 s
    assert g.multiplier(130, shout=True) == 1.0


def test_loudness_proxy_flat_vs_bursty():
    flat, burst = DeadAirGate(P), DeadAirGate(P)
    for i in range(40):
        flat.add_loudness(i * 0.5, -20.0)                         # steady music
        burst.add_loudness(i * 0.5, -18.0 if i % 2 else -32.0)    # speech-like swing
    assert flat.show_start is None and burst.show_start is not None


def test_detector_gate_rejects_pre_show_moment():
    msgs = [(float(t), f"u{t % 7}", "hi") for t in range(0, 400)]
    msgs = sorted(msgs + [(300 + i * 0.05, f"x{i}", "KEKW") for i in range(200)])   # spike at 300 s
    plain, _ = replay(msgs, DetectorParams(), DEFAULT_REACTIONS)
    gated, det = replay(msgs, DetectorParams(), DEFAULT_REACTIONS, gate=DeadAirGate(P))
    assert plain and not gated
    assert det.rejected and det.rejected[0][1] == "dead air: before show_start"


def test_detector_gate_keeps_moment_after_show_start():
    msgs = [(float(t), f"u{t % 7}", "hi") for t in range(0, 400)]
    msgs = sorted(msgs + [(300 + i * 0.05, f"x{i}", "KEKW") for i in range(200)])
    loud = [(t * 0.5, -18.0 if t % 2 else -32.0) for t in range(0, 800)]   # talking all stream
    gated, _ = replay(msgs, DetectorParams(), DEFAULT_REACTIONS, loudness=loud, gate=DeadAirGate(P))
    assert gated and gated[0].features["dead_air_mult"] == 1.0


def test_transcript_quiet_and_dead_air_ratio():
    words = [Word(1.0, 1.5, "yo"), Word(2.0, 2.5, "what")]
    assert not words_quiet(words, 10.0, P) and words_quiet(words, 40.0, P)
    assert dead_air_ratio(words, 0, 10) == pytest.approx(1 - 2.5 / 10)
    assert dead_air_ratio([], 0, 10) == 1.0 and dead_air_ratio(words, 5, 5) == 0.0


def test_frame_reject_parses_ffmpeg_log():
    log = ("[blackdetect @ 0] black_start:0 black_end:12 black_duration:12\n"
           "[freezedetect @ 0] lavfi.freezedetect.freeze_duration: 3.5\n")
    assert parse_frame_log(log) == (12.0, 3.5)

    class R:
        def __init__(self, err): self.stderr = err
    assert "black" in frame_reject(Path("x.mp4"), 20, P, run=lambda *a, **k: R(log))
    frozen = "lavfi.freezedetect.freeze_duration: 15\n"
    assert "frozen" in frame_reject(Path("x.mp4"), 20, P, run=lambda *a, **k: R(frozen))
    assert frame_reject(Path("x.mp4"), 20, P, run=lambda *a, **k: R("")) is None


# --- 0-100 score -----------------------------------------------------------------------
def test_score_parts():
    assert sc.length_part(15) == 10 and sc.length_part(8) == 0 and sc.length_part(60) == 0
    assert 0 < sc.length_part(40) < 10 and sc.length_part(25, min_s=30) == 0
    assert sc.hook_part(1.0) == 15 and sc.hook_part(8.0) == 0 and sc.hook_part(None) == 0
    assert sc.peak_part(5.0, [1, 2, 3, 4, 6], 2.5) == pytest.approx(12.0)   # 4 of 5 below
    assert sc.peak_part(5.0, [], 2.5) == 15 and sc.peak_part(2.5, [], 2.5) == 0
    assert sc.density_part(3, 3, 2) == 10 and sc.density_part(0, 0, 0) == 0
    assert sc.score_10(65) == 7 and sc.score_10(64) == 6 and sc.score_10(3) == 1


def test_score_total_bonus_and_clamp():
    meas = {"peak": 15, "hook_speed": 15, "length": 10, "density": 10}
    judg = {k: 10 for k in sc.JUDGED_PARTS}
    assert sc.total(meas, judg, viewers_clipped=True)[0] == 100            # capped
    t, bonus = sc.total(meas, judg, dead_air_ratio=0.5)
    assert t == 85 and bonus == {"viewers_clipped": 0, "dead_air": -15}
    assert sc.judged({"hook": 14, "payoff": "x"}) == {"hook": 10, "payoff": 0, "standalone": 0,
                                                      "emotion": 0, "share": 0}


def test_schema_100_extends_and_keeps_score_10():
    assert "score_10" in SCHEMA_100["required"] and "parts" in SCHEMA_100["required"]
    assert set(SCHEMA_100["required"]) <= set(SCHEMA_100["properties"])
    assert "parts" not in SCHEMA["required"] and SYSTEM_100.startswith(SYSTEM)


def test_validate_reads_parts():
    j = validate({**RAW, "parts": {**PARTS, "hook": 99}, "send_test": " my brother: LMAO ",
                  "why": "big payoff", "proof_frame_ts": 400}, 40, 10, 60)
    assert j.parts["judged"]["hook"] == 10 and j.send_test == "my brother: LMAO"
    assert j.proof_frame_ts == j.trim_out                                # clamped into the cut
    assert validate(RAW, 40, 10, 60).parts == {}                         # flag off: nothing new


def test_grok_uses_100_prompt_only_when_on(tmp_path):
    calls = []

    def handler(req):
        calls.append(json.loads(req.content))
        raw = {**RAW, "parts": PARTS, "send_test": "a", "why": "b", "proof_frame_ts": 6}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(raw)}}]})
    http = httpx.Client(transport=httpx.MockTransport(handler))
    GrokJudge("k", "m", tmp_path / "a", http).judge([], [], {}, "", 40)
    GrokJudge("k", "m", tmp_path / "b", http, score_100=True).judge([], [], {}, "", 40)
    assert calls[0]["messages"][0]["content"] == SYSTEM
    assert calls[1]["messages"][0]["content"] == SYSTEM_100
    assert "parts" in calls[1]["response_format"]["json_schema"]["schema"]["required"]


# --- pipeline wiring -------------------------------------------------------------------
WORDS = [Word(5 + i * 0.4, 5.3 + i * 0.4, w) for i, w in
         enumerate("bro no way KEKW he just hit that from across the whole map".split())]


class J:
    def __init__(self, parts=PARTS, send="my squad: bro"):
        self.parts, self.send, self.n = parts, send, 0

    def cost_usd(self, usage):
        return 0.0

    def judge(self, words, chat, scores, rules, dur, min_len, max_len):
        self.n += 1
        raw = {**RAW}
        if self.parts is not None:
            raw.update(parts=self.parts, send_test=self.send, why="w", proof_frame_ts=8)
        return validate(raw, dur, min_len, max_len, words)


def _pipe(tmp_path, judge, features, frames=lambda v, d: None, words=WORDS):
    sb = FakeSupabase()
    sb.insert("campaigns", {"id": "c", "title": "t", "status": "active", "streamer_slugs": ["lacy"],
                            "platforms": ["youtube"], "score": 4, "rules": {"min_s": 10, "max_s": 60}})
    ch = Channel("twitch:lacy", "twitch", "lacy", "lacy", None, DEFAULT_REACTIONS, DetectorParams())
    s = Settings(work_dir=tmp_path, channels=[ch], caption_style=None, features=features)
    store = Store(":memory:")
    pipe = Pipeline(s, store, RightsGate(sb.active_campaigns), None, judge, None, frames=frames)
    jid = pipe.on_moment(Moment("twitch:lacy", 1000, 1003, 4.0, 1005, 975, 1015, {"z_audio": 0.0}))
    store.advance(jid, "captured", {"capture": {"video": "v.mp4", "audio": "a.wav", "start_ts": 990,
                                                "end_ts": 1030}})
    store.advance(jid, "transcribed", {"words": [w.__dict__ for w in words], "transcript": ""})
    pipe._judge(store.job(jid))
    return store.job(jid), judge


def test_pipeline_flags_off_is_unchanged(tmp_path):
    job, _ = _pipe(tmp_path, J(), Features())
    j = job.data["judgment"]
    assert job.stage == "judged" and j["score"] is None and j["score_10"] == 8


def test_pipeline_score_100_on(tmp_path):
    job, _ = _pipe(tmp_path, J(), Features(score_100=True))
    j = job.data["judgment"]
    assert job.stage == "judged" and 60 <= j["score"] <= 100
    assert j["score_10"] == sc.score_10(j["score"]) and sum(j["parts"]["judged"].values()) == 42
    assert set(j["parts"]["measured"]) == {"peak", "hook_speed", "length", "density"}


def test_pipeline_score_100_drops_weak_and_no_send_test(tmp_path):
    job, _ = _pipe(tmp_path, J(parts={k: 2 for k in PARTS}), Features(score_100=True))
    assert job.stage == "dropped" and "below 60" in job.data["judgment"]["reason"]
    job, _ = _pipe(tmp_path, J(send=""), Features(score_100=True))
    assert job.stage == "dropped" and "send test" in job.data["judgment"]["reason"]


def test_pipeline_heuristic_judge_scores_but_never_drops(tmp_path):
    job, _ = _pipe(tmp_path, J(parts=None), Features(score_100=True))
    j = job.data["judgment"]
    assert job.stage == "judged" and j["parts"]["judged"] is None and j["score"] < 60


def test_pipeline_dead_air_drops_before_judge(tmp_path):
    job, judge = _pipe(tmp_path, J(), Features(dead_air_gate=True), words=[])   # silent window
    assert job.stage == "dropped" and judge.n == 0 and "dead air" in job.data["dead_air"]
    job, judge = _pipe(tmp_path, J(), Features(dead_air_gate=True),
                       frames=lambda v, d: "dead air: 90% black frames")
    assert job.stage == "dropped" and judge.n == 0
    job, judge = _pipe(tmp_path, J(), Features(dead_air_gate=True))
    assert job.stage == "judged" and judge.n == 1
