"""Long-form TikTok pipeline (D079-D082): planner, schedule, script checks, timeline, render, QA, runner."""
import json
import subprocess
from datetime import date
from pathlib import Path

import pytest

from clipworker.config import DEFAULT_REACTIONS, Channel, Crop, DetectorParams, Settings
from clipworker.longform.plan import Beat, Plan, Schedule, Tags, assemble, beat_from_job, kill_check
from clipworker.longform.qa_long import check_long
from clipworker.longform.render_long import build_captions, render_long
from clipworker.longform.runner import LongformRunner
from clipworker.longform.script import ScriptError, budgets, feasible, validate
from clipworker.longform.timeline import TimelineError, build
from clipworker.longform.voice import Line, voice_lines
from clipworker.store import Job, Store

from conftest import TEST_LAYOUT, TEST_STYLE, needs_ffmpeg
from fakes import FakeSupabase

NOW = 100_000.0
TRANSCRIPT = "bro what is he doing right now he just drove off the bridge again chat"


def _job(i, video="v.mp4", score=8, trim=(10.0, 28.0), campaign=None, streamer_ch="twitch:lacy", ts=None):
    cap = {"video": video, "audio": video, "start_ts": 1000.0 * i, "end_ts": 1000.0 * i + 30}
    words = [{"start": 10.0 + k * 0.5, "end": 10.4 + k * 0.5, "text": w}
             for k, w in enumerate(TRANSCRIPT.split())]
    data = {"capture": cap, "peak_ts": cap["start_ts"] + trim[0] + 3, "transcript": TRANSCRIPT,
            "words": words, "chat_sample": ["KEKW", "NO WAY", "he did it again"], "campaign_id": campaign,
            "judgment": {"keep": True, "trim_in": trim[0], "trim_out": trim[1], "score_10": score,
                         "title": f"Lacy bridge {i}", "hook": "He drove off the bridge"}}
    return Job(f"j{i}", streamer_ch, "uploaded", cap["start_ts"], cap["end_ts"],
               ts if ts is not None else NOW - 3600 * i, 4.0, data, None, 0, None)


def _beats(video="v.mp4"):
    jobs = [_job(1, video, 9, (10.0, 28.0)), _job(2, video, 8, (15.0, 28.0)), _job(3, video, 7, (15.0, 28.0))]
    return [beat_from_job(j, "lacy") for j in jobs]


def _script_raw(plan, extra_words=0):
    h, bs, o = budgets(plan)
    say = lambda n: " ".join(["story"] * n)
    return {"headline": "Lacy Bridge Again", "hook": say(h), "beats": [say(max(1, b - 2) + extra_words) for b in bs],
            "outro": "would you drive again", "title": "Lacy cannot stop driving off bridges",
            "caption": "Lacy's worst drive yet", "hashtags": ["lacy", "#gta6"]}


# ---- planner -------------------------------------------------------------------------

def test_beat_skips_sponsored_weak_and_unjudged():
    assert beat_from_job(_job(1, campaign="camp1"), "lacy") is None          # D081
    assert beat_from_job(_job(1, score=5), "lacy") is None
    j = _job(1)
    j.data["judgment"] = {}
    assert beat_from_job(j, "lacy") is None
    b = beat_from_job(_job(1), "lacy")
    assert (b.t_in, b.t_out, b.lead_in_s, b.peak_rel) == (2.0, 28.0, 8.0, 11.0)


def test_assemble_reaches_one_minute_in_time_order():
    plan = assemble(_beats(), Tags(), set(), NOW)
    assert plan is not None
    assert 61 <= plan.est_runtime() <= 75
    assert [b.job_id for b in plan.beats] == ["j3", "j2", "j1"]      # oldest moment first
    assert assemble(_beats(), Tags(), {"j1", "j2"}, NOW) is None          # used clips never repeat
    assert assemble(_beats(), Tags(), set(), NOW + 10 * 86400) is None    # stale


def test_topn_counts_down():
    plan = assemble(_beats(), Tags(format="topn"), set(), NOW)
    assert [b.score_10 for b in plan.beats] == [7, 8, 9]


def test_schedule_weeks_and_kill_rule():
    s = Schedule(start=date(2026, 11, 23))
    first = {(s.tags_for(date(2026, 11, 23 + d), k).format, s.tags_for(date(2026, 11, 23 + d), k).pacing)
             for d in range(4) for k in (0, 1)}
    assert len(first) == 8                                               # every format x pacing cell
    s3 = Schedule(start=date(2026, 11, 23), lead_format="recap", lead_pacing="short")
    a, b = s3.tags_for(date(2026, 12, 7), 0), s3.tags_for(date(2026, 12, 7), 1)
    assert (a.caption_style, b.caption_style) == ("A", "B")              # week 3: D073 test
    assert kill_check({"recap": 1, "extended": 2}) == ["extended"]
    with pytest.raises(ValueError):
        Schedule(start=date(2026, 11, 23), disabled_formats=("recap", "topn", "explainer", "extended")
                 ).tags_for(date(2026, 11, 23), 0)


# ---- script checks -------------------------------------------------------------------

def test_script_validation():
    plan = assemble(_beats(), Tags(), set(), NOW)
    assert feasible(plan)[0]
    s = validate(_script_raw(plan), plan)
    assert s.cards == ["", "", ""] and s.hashtags == ["#lacy", "#gta6"]
    with pytest.raises(ScriptError, match="over budget"):
        validate(_script_raw(plan, extra_words=10), plan)
    raw = _script_raw(plan)
    raw["beats"][0] = "he just drove off the bridge again"                # 6-gram from transcript
    with pytest.raises(ScriptError, match="copies"):
        validate(raw, plan)
    raw = _script_raw(plan)
    raw["beats"][1] = "this is his 47th crash"
    with pytest.raises(ScriptError, match="numbers"):
        validate(raw, plan)


# ---- timeline --------------------------------------------------------------------------

def _lines(plan, script, per_word=0.38):
    out = [Line("hook", script.hook, "hook.wav", len(script.hook.split()) * per_word)]
    out += [Line(f"beat{i + 1}", t, f"b{i}.wav", len(t.split()) * per_word) for i, t in enumerate(script.beats)]
    return out + [Line("outro", script.outro, "outro.wav", len(script.outro.split()) * per_word)]


def test_timeline_pieces_coverage_and_overrun():
    plan = assemble(_beats(), Tags(), set(), NOW)
    s = validate(_script_raw(plan), plan)
    tl = build(plan, _lines(plan, s), has_layout=True)
    assert tl.total_s > 60.5 and tl.coverage >= 0.4
    modes = [p.mode for p in tl.pieces if p.beat == 0]
    assert modes == ["game", "stacked", "cam"]                            # switch layout by beat
    assert build(Plan(**{**plan.__dict__, "tags": Tags(layout="stacked")}), _lines(plan, s), True).pieces[0].mode == "stacked"
    with pytest.raises(TimelineError, match="into the moment"):
        build(plan, _lines(plan, s, per_word=0.8), has_layout=True)


# ---- render + QA (real ffmpeg) -----------------------------------------------------------

def _sine_voice(tmp_path):
    class V:
        def speak(self, text, out):
            out.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                            f"sine=frequency=220:sample_rate=48000:duration={len(text.split()) * 0.36:.2f}",
                            str(out)], check=True)
    return V()


@needs_ffmpeg
def test_render_long_passes_qa(tmp_path, source_video):
    for style in ("A", "B"):
        plan = assemble(_beats(str(source_video)), Tags(caption_style=style), set(), NOW)
        s = validate(_script_raw(plan), plan)
        lines = voice_lines(s, _sine_voice(tmp_path), tmp_path / style / "voice")
        tl = build(plan, lines, has_layout=True)
        m = render_long(plan, s, tl, TEST_LAYOUT, TEST_STYLE, tmp_path / style / "out")
        res = check_long(Path(m["video"]), tmp_path / style / "out" / "captions.ass", m, TEST_LAYOUT,
                         title=s.title, description=s.caption)
        assert res.passed, res.failures
        assert res.metrics["width"] == 1080 and res.metrics["duration"] > 60.5
        ass = (tmp_path / style / "out" / "captions.ass").read_text(encoding="utf-8")
        assert "LACY BRIDGE AGAIN" in ass
        assert ("bridge" in ass.lower().split("[events]")[1].replace("lacy bridge again", "")) == (style == "B")


def test_qa_long_flags_originality_and_logos(tmp_path, source_video):
    m = {"coverage": 0.2, "max_silent_run_s": 30.0}
    res = check_long(source_video, None, m, TEST_LAYOUT, logo_boxes=[Crop(0, 0, 100, 100)])
    text = " ".join(res.failures)
    assert "narration covers 20%" in text and "30s stretch" in text and "watermark" in text
    assert "not over 60.5s" in text


# ---- runner ------------------------------------------------------------------------------

class FakeWriter:
    def __init__(self):
        self.calls = 0

    def write(self, plan):
        self.calls += 1
        s = validate(_script_raw(plan), plan)
        s.usage = {"total_tokens": 900}
        return s

    def cost_usd(self, usage):
        return 0.002


@needs_ffmpeg
def test_runner_end_to_end_into_review_queue(tmp_path, source_video):
    ch = Channel("twitch:lacy", "twitch", "lacy", "lacy", TEST_LAYOUT, DEFAULT_REACTIONS, DetectorParams())
    st = Store(":memory:")
    for i, (sc, tr) in enumerate([(9, (10.0, 28.0)), (8, (15.0, 28.0)), (7, (15.0, 28.0))], 1):
        j = _job(i, str(source_video), sc, tr)
        st.create_job(j.id, j.channel, j.start_ts, j.end_ts, j.trigger_ts, 4.0, j.data, None)
        st.db.execute("UPDATE jobs SET stage='uploaded' WHERE id=?", (j.id,))
    st.db.commit()
    sb = FakeSupabase()
    sb.t["longform_videos"] = []
    sb.insert("streamers", {"id": "s-lacy", "slug": "lacy"})
    settings = Settings(work_dir=tmp_path, channels=[ch], caption_style=TEST_STYLE)
    # schedule pinned to a recap/short day so the 30 s test captures can fill it
    (tmp_path / "longform").mkdir()
    (tmp_path / "longform" / "schedule.json").write_text(json.dumps(
        {"start": "2026-01-01", "disabled_formats": ["topn", "explainer", "extended"]}), encoding="utf-8")
    w = FakeWriter()
    r = LongformRunner(settings, st, w, _sine_voice(tmp_path), sb, clock=lambda: NOW)
    r.schedule = lambda: Schedule(start=r._today(), disabled_formats=("topn", "explainer", "extended"))
    r.run_once()
    plans = r.plans()
    assert len(plans) == 1 and plans[0].state == "uploaded", (plans[0].state, plans[0].error, plans[0].qa)
    clip = sb.t["clips"][0]
    assert clip["category"] == "longform" and clip["state"] == "pending_review" and clip["duration_s"] > 60
    v = sb.t["longform_videos"][0]
    assert (v["format"], v["pacing"], v["caption_style"], v["voice"], v["layout"]) == ("recap", "short", "A", "ai", "switch")
    assert sb.t["spend"] and w.calls == 1
    assert r.plan_today() is None            # moments used up; never reused


def test_runner_waits_without_model_or_recording(tmp_path):
    ch = Channel("twitch:lacy", "twitch", "lacy", "lacy", TEST_LAYOUT, DEFAULT_REACTIONS, DetectorParams())
    r = LongformRunner(Settings(work_dir=tmp_path, channels=[ch], caption_style=TEST_STYLE), Store(":memory:"),
                       None, None, None, clock=lambda: NOW)
    plan = assemble(_beats(), Tags(voice="zo"), set(), NOW)
    r.save(plan)
    assert r.step(plan) is False and plan.state == "planned"              # no narration, no video
    plan.script, plan.state = validate(_script_raw(plan), plan).__dict__, "scripted"
    assert r.step(plan) is False and plan.state == "needs_recording"


def test_publisher_leaves_long_videos_for_manual_tiktok_upload():
    from clipworker.publish.runner import PublishRunner
    sb = FakeSupabase()
    sb.insert("clips", {"job_id": "long-p1", "state": "approved", "category": "longform", "channel_key": "twitch:lacy"})
    PublishRunner(sb, {}, lambda c: "x.mp4").run_once()
    assert sb.t["clips"][0]["state"] == "approved"
