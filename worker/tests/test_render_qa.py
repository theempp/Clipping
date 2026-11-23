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
    assert "{\\b1}{\\c&H0000FFFF}shot{\\c&H00FFFFFF}{\\b0}" in ass  # emphasis: bold + colour
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
    for frag in ("rights", "duration", "#clix", "banned word", "hook"):
        assert frag in text, text


def test_groups_break_on_punctuation_pause_and_width():
    from dataclasses import replace

    from clipworker.render.captions import group_words
    ws = [Word(0.0, 0.2, "no"), Word(0.2, 0.4, "way,"), Word(0.4, 0.6, "he"), Word(0.6, 0.8, "hit"),
          Word(1.5, 1.7, "that"), Word(1.7, 1.9, "shot")]
    g = [[w.text for w in grp] for grp in group_words(ws, TEST_STYLE)]
    assert g == [["no", "way,"], ["he", "hit"], ["that", "shot"]]   # comma, then 0.7 s pause
    big = replace(TEST_STYLE, size=160)
    long = [Word(i, i + 0.5, "unbelievable") for i in range(3)]
    assert all(len(x) == 1 for x in group_words(long, big))           # would overflow 960 px


def test_pop_animates_active_word_only():
    from dataclasses import replace
    ass = build_ass(shift_words(WORDS, 3.0, 20.0), replace(TEST_STYLE, pop_scale=115, pop_ms=90))
    line = [x for x in ass.splitlines() if x.startswith("Dialogue:")][0]
    assert "\\fscx115\\fscy115\\t(0,90,\\fscx100\\fscy100)" in line
    assert line.count("fscx115") == 1
    assert "fscx" not in build_ass(shift_words(WORDS, 3.0, 20.0), TEST_STYLE)  # off by default


@needs_ffmpeg
def test_qa_flags_caption_overflow(source_video, tmp_path):
    from clipworker.render.captions import ass_time
    render_clip("clip3", source_video, tmp_path / "r", 3.0, 18.0, WORDS, TEST_LAYOUT, TEST_STYLE)
    cap = tmp_path / "r" / "captions.ass"
    rules = CampaignRules(min_s=10, max_s=60, permitted=True)
    ok = check_clip(tmp_path / "r" / "clip.mp4", cap, rules, title="t")
    assert 0 < ok.metrics["caption_max_width_px"] <= 960
    assert not [f for f in ok.failures if "overflows" in f]
    cap.write_text(cap.read_text(encoding="utf-8")
                   + f"Dialogue: 0,{ass_time(1)},{ass_time(2)},Cap,,0,0,0,,{'W' * 40}\n", encoding="utf-8")
    bad = check_clip(tmp_path / "r" / "clip.mp4", cap, rules, title="t")
    assert any("overflows" in f for f in bad.failures)


def test_flash_counter():
    from clipworker.qa import max_flashes_per_s
    strobe = [(i / 30, 235.0 if (i // 3) % 2 else 16.0) for i in range(90)]   # 5 flashes/s
    assert max_flashes_per_s(strobe) > 3
    cuts = [(i / 30, 200.0 if i >= 45 else 40.0) for i in range(90)]            # one hard cut
    assert max_flashes_per_s(cuts) <= 1


@needs_ffmpeg
def test_qa_flags_flashing_small_text_and_late_hook(source_video, tmp_path):
    import re
    import subprocess
    render_clip("clip4", source_video, tmp_path / "r", 3.0, 18.0, WORDS, TEST_LAYOUT, TEST_STYLE)
    rules = CampaignRules(min_s=10, max_s=60, permitted=True)
    ok = check_clip(tmp_path / "r" / "clip.mp4", tmp_path / "r" / "captions.ass", rules, title="t")
    assert ok.metrics["max_flashes_per_s"] <= 3 and ok.metrics["hook_s"] <= 3
    cap = tmp_path / "r" / "captions.ass"
    cap.write_text(re.sub(r"^(Style: Cap,[^,]*,)\d+,", r"\g<1>40,", cap.read_text(encoding="utf-8"),
                          flags=re.M), encoding="utf-8")
    late = CampaignRules(min_s=10, max_s=60, permitted=True, hook_s=0.5)
    bad = check_clip(tmp_path / "r" / "clip.mp4", cap, late, title="t")
    text = " | ".join(bad.failures)
    assert "too small" in text and "hook" in text, text
    strobe = tmp_path / "strobe.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    "color=black:s=1080x1920:r=30:d=12,geq=lum='if(mod(floor(T*10),2),235,16)':cb=128:cr=128",
                    "-f", "lavfi", "-i", "sine=f=440:d=12", "-shortest", "-pix_fmt", "yuv420p", str(strobe)],
                   check=True)
    res = check_clip(strobe, None, rules, title="t")
    assert any("flashes/s" in f for f in res.failures), res.failures
