from conftest import TEST_LAYOUT, TEST_STYLE, needs_ffmpeg

from clipworker.config import SfxParams, ZoomParams, parse_settings
from clipworker.qa import CampaignRules, check_clip
from clipworker.remote.rights import rules_from
from clipworker.render.ffmpeg import render_clip
from clipworker.render.sfx import audio_filter, ensure_whoosh
from clipworker.transcribe import Word

ON = SfxParams(enabled=True)


def test_audio_filter_off_and_on():
    assert audio_filter([2.0], SfxParams()) == ("[0:a:0]loudnorm=I=-14:TP=-1.5:LRA=11[a]", False)
    assert audio_filter([], ON)[1] is False
    g, used = audio_filter([2.0, 7.5], ON)
    assert used and "asplit=2[w0][w1]" in g and "adelay=1850|1850" in g and "adelay=7350|7350" in g
    assert "amix=inputs=3:duration=first:normalize=0,loudnorm" in g


def test_settings_and_campaign_flags(tmp_path):
    assert not parse_settings({}, tmp_path).sfx.enabled
    assert parse_settings({"sfx": {"enabled": True}}, tmp_path).sfx.enabled
    assert rules_from({"rules": {"allow_sfx": False}}).allow_sfx is False
    assert rules_from({}).allow_sfx is True


@needs_ffmpeg
def test_whoosh_synth_cached(tmp_path):
    a = ensure_whoosh(tmp_path)
    m = a.stat().st_mtime_ns
    assert ensure_whoosh(tmp_path) == a and a.stat().st_mtime_ns == m


@needs_ffmpeg
def test_render_with_sfx_passes_loudness_qa(source_video, tmp_path):
    words = [Word(0.5, 0.9, "no"), Word(0.9, 1.4, "way."), Word(6.0, 6.5, "again."), Word(9.0, 9.4, "end")]
    m = render_clip("s1", source_video, tmp_path / "r", 3.0, 18.0, words, TEST_LAYOUT, TEST_STYLE,
                    zoom=ZoomParams(scale=1.3), sfx=ON)
    assert m["sfx"] is True and m["zooms"]
    res = check_clip(tmp_path / "r" / "clip.mp4", tmp_path / "r" / "captions.ass",
                     CampaignRules(min_s=10, max_s=60, permitted=True), title="t")
    assert res.passed, res.failures
