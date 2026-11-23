import json
import shutil
import subprocess
from pathlib import Path

from conftest import TEST_LAYOUT, needs_ffmpeg
from test_pipeline import _env, _moment

from clipworker.render import flashback as FBK
from clipworker.render import sfxlib, tools as T
from clipworker.transcribe import Word


def W(text, t):
    return Word(t, t + 0.4, text)


def test_content_words_skip_filler():
    cw = FBK.content_words([W("this", 1), W("Rocket", 2), W("league", 3), W("yeah", 4), W("it", 5)])
    assert set(cw) == {"rocket", "league"}


def test_proposal_needs_three_shared_words_and_a_real_file(tmp_path, source_video):
    pipe, sb, store = _env(tmp_path, source_video)
    vid = tmp_path / "old.mp4"
    shutil.copy(source_video, vid)
    old = [W("rocket", 3), W("league", 4), W("championship", 5), W("overtime", 6)]
    store.create_job("old1", "twitch:lacy", 100, 130, 110, 3.0,
                     {"words": [w.__dict__ for w in old], "capture": {"video": str(vid)},
                      "judgment": {"title": "Overtime goal"}}, "k1")
    cur = [W("rocket", 1), W("league", 2), W("championship", 3), W("again", 4)]
    p = FBK.propose(store, "twitch:lacy", cur, 5000.0)
    assert p and p["source_job"] == "old1" and p["source_file"] == str(vid) and p["start"] == 2.5
    assert "rocket" in p["reason"] and "Overtime goal" in p["reason"]
    assert FBK.propose(store, "twitch:lacy", cur[:2], 5000.0) is None           # too few shared words
    assert FBK.propose(store, "twitch:clix", cur, 5000.0) is None               # other streamer
    assert FBK.propose(store, "twitch:lacy", cur, 5000.0, exclude_job="old1") is None
    vid.unlink()
    assert FBK.propose(store, "twitch:lacy", cur, 5000.0) is None               # file gone


def test_vhs_graph_has_rewind_look_and_no_zoom():
    g = FBK.vhs_graph(TEST_LAYOUT, 2.8)
    assert "reverse" in g and "noise=" in g and "rgbashift" in g and "drawgrid" in g
    assert "zoompan" not in g and g.endswith("[v]")


def test_shift_time_follows_slowmo_and_inserts():
    fx = [("slowmo_vignette", 2.0, 1.0, 0.5), ("flashback", 5.0, 1.4, 1.0)]
    assert T.shift_time(1.0, fx) == 1.0
    assert T.shift_time(2.5, fx) == 3.0                    # inside slow-mo: 2 + 0.5/0.5
    assert abs(T.shift_time(3.5, fx) - 4.5) < 1e-9          # after slow-mo: + 1.0
    assert abs(T.shift_time(6.0, fx) - 8.4) < 1e-9          # after slow-mo and flashback insert


@needs_ffmpeg
def test_sfx_library_synthesizes_and_caches(tmp_path):
    for name in ("hit", "glitch", "rewind", "whoosh"):
        p = sfxlib.ensure_sfx(name, tmp_path)
        assert p.exists() and p.stat().st_size > 2000
        m = p.stat().st_mtime_ns
        assert sfxlib.ensure_sfx(name, tmp_path).stat().st_mtime_ns == m


def _probe_dur(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", str(p)],
                       check=True, capture_output=True, text=True)
    return float(json.loads(r.stdout)["format"]["duration"])


@needs_ffmpeg
def test_flashback_renders_into_clip_with_rewind_sound(source_video, tmp_path):
    from test_tools import make_clip
    clip = tmp_path / "clip.mp4"
    make_clip(clip, 6)
    prop = {"source_file": str(source_video), "start": 2.0, "length": 2.8}
    new = FBK.render_flashback(clip, prop, 6.0, 3.0, TEST_LAYOUT, tmp_path / "sfx")
    assert abs(new - 7.4) < 0.01 and abs(_probe_dur(clip) - 7.4) < 0.3
    assert not list(tmp_path.glob("*.fb*.mp4"))


@needs_ffmpeg
def test_sfx_mix_adds_sounds_and_keeps_length(tmp_path):
    from test_tools import make_clip
    clip = tmp_path / "clip.mp4"
    make_clip(clip, 5)
    hit, glitch = sfxlib.ensure_sfx("hit", tmp_path / "s"), sfxlib.ensure_sfx("glitch", tmp_path / "s")
    dur = T.apply_effects(clip, [{"tool": "sfx", "hits": [(str(hit), 1.0, -8), (str(glitch), 3.0, -12)]}], 5.0)
    assert dur == 5.0 and abs(_probe_dur(clip) - 5.0) < 0.3
