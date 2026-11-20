import dataclasses

import pytest

from clipworker.qa import CampaignRules, check_clip
from clipworker.render.captions import build_ass, parse_ass_events, shift_words
from clipworker.render.ffmpeg import render_clip, video_filter
from clipworker.transcribe import Word

from conftest import TEST_LAYOUT, TEST_STYLE, needs_ffmpeg

WORDS = [Word(4.0 + i * 0.4, 4.35 + i * 0.4, w) for i, w in
         enumerate("no way he actually hit that shot from across the map {bro}".split())]


def test_shift_words_rebases_and_drops_outside():
    out = shift_words(WORDS, 5.0, 6.0)
    assert out[0].start == 0.0 or out[0].start < 0.4
    assert all(0 <= w.start < 1.0 for w in out)


def test_ass_highlight_one_event_per_word():
    ass = build_ass(shift_words(WORDS, 3.0, 20.0), TEST_STYLE, emphasis=["shot"])
    ev = parse_ass_events(ass)
    assert len(ev) == len(WORDS)
    assert all(e > s for s, e in ev)
    assert all(b[0] >= a[0] for a, b in zip(ev, ev[1:]))   # ordered
    assert "{\\b1}shot{\\b0}" in ass
    assert "(bro)" in ass  # braces escaped, can't inject ASS overrides
    assert "PlayResY: 1920" in ass


def test_caption_safe_area_enforced():
    bad = dataclasses.replace(TEST_STYLE, margin_v=100)
    with pytest.raises(ValueError, match="safe area"):
        build_ass(WORDS, bad)


def test_filter_graphs():
    assert "vstack" in video_filter(TEST_LAYOUT, "captions.ass")
    assert video_filter(None, None).startswith("[0:v]crop=ih*9/16")
    assert video_filter(None, "captions.ass").endswith("ass=captions.ass[v]")


def test_render_refuses_without_style(tmp_path):
    with pytest.raises(ValueError, match="D022"):
        render_clip("c", tmp_path / "x.mp4", tmp_path, 0, 10, [], None, None)


@needs_ffmpeg
def test_render_and_qa_pass(source_video, tmp_path):
    m = render_clip("clip1", source_video, tmp_path / "r", 3.0, 18.0, WORDS, TEST_LAYOUT, TEST_STYLE,
                    ["shot"], hook_offset=2.0, manifest_extra={"tags": ["#lacy"]})
    assert m["fps"] == 30 and abs(m["duration"] - 15.0) < 0.01
    assert (tmp_path / "r" / "thumb.jpg").stat().st_size > 0
    rules = CampaignRules(min_s=10, max_s=60, required_tags=["#lacy"], permitted=True)
    res = check_clip(tmp_path / "r" / "clip.mp4", tmp_path / "r" / "captions.ass", rules,
                     title="He hit THAT", description="#lacy")
    assert res.passed, res.failures
    assert res.metrics["width"] == 1080 and res.metrics["height"] == 1920
    assert -16.5 <= res.metrics["lufs"] <= -11.5


@needs_ffmpeg
def test_qa_reports_every_failure(source_video, tmp_path):
    render_clip("clip2", source_video, tmp_path / "r", 0.0, 8.0, WORDS, None, TEST_STYLE)
    rules = CampaignRules(min_s=10, max_s=60, required_tags=["#clix"], banned_words=["kick"],
                          permitted=False)
    res = check_clip(tmp_path / "r" / "clip.mp4", tmp_path / "r" / "captions.ass", rules,
                     title="watch on kick")
    text = " | ".join(res.failures)
    assert not res.passed
    for frag in ("rights", "duration", "#clix", "banned word"):
        assert frag in text, text
