import subprocess
from pathlib import Path

import pytest

from clipworker.config import ConfigError, ZoomParams, parse_settings
from clipworker.render import motion
from clipworker.render.ffmpeg import render_clip
from clipworker.render.motion import (detect_cuts, shot_centres, shots, track_crop_filter,
                                      zoom_expr, zoom_times)
from clipworker.transcribe import Word

from conftest import TEST_LAYOUT, TEST_STYLE, needs_ffmpeg

Z = ZoomParams(scale=1.2)
WORDS = [Word(0.5, 0.9, "no"), Word(0.9, 1.4, "way."), Word(1.6, 2.0, "he"), Word(2.0, 2.5, "did"),
         Word(2.5, 3.0, "it!"), Word(5.0, 5.5, "chat"), Word(5.5, 6.0, "look"), Word(7.0, 7.5, "again."),
         Word(12.0, 12.5, "last."), Word(14.6, 14.9, "end")]


def test_zoom_off_by_default():
    assert zoom_times(WORDS, 15, ZoomParams()) == [] and not ZoomParams().on


def test_zoom_times_sentence_ends_spaced_and_peak_first():
    t = zoom_times(WORDS, 15, Z)
    assert t == [1.4, 6.0, 12.5]   # 3.0 too close to 1.4; 6.0 = pause; 7.5 too close; 14.9 runs past end
    t = zoom_times(WORDS, 15, Z, peak=3.0)
    assert 3.0 in t and 1.4 not in t                 # peak wins its 4 s neighbourhood
    assert all(b - a >= 4 for a, b in zip(t, t[1:]))


def test_zoom_expr_is_trapezoid():
    e = zoom_expr([2.0], Z)
    f = lambda it: 1 + 0.2 * min(max((it - 2.0) / 0.2, 0), 1) * min(max((3.6 - it) / 0.2, 0), 1)
    assert e.startswith("1+0.2000*(clip((it-2.000)/0.200,0,1)*clip((3.600-it)/0.200,0,1))")
    assert f(1.0) == 1 and f(2.5) == pytest.approx(1.2) and f(3.7) == 1
    assert zoom_expr([], Z) == "1"


def test_settings_zoom_validation(tmp_path):
    s = parse_settings({"zoom": {"scale": 1.2}}, tmp_path)
    assert s.zoom.on and s.zoom.scale == 1.2
    with pytest.raises(ConfigError):
        parse_settings({"zoom": {"scale": 1.2, "min_gap_s": 1.0}}, tmp_path)


def test_shots_and_track_filter():
    assert shots([4.0, 9.0], 12) == [(0.0, 4.0), (4.0, 9.0), (9.0, 12)]
    f = track_crop_filter([(0, 4, 0.2), (4, 12, 0.8)])
    assert f.startswith("crop=ih*9/16:ih:x='if(lt(t,4.000),max(0,min(iw-ow,0.2000*iw-ow/2))")
    assert track_crop_filter([]) == "crop=ih*9/16:ih"


@pytest.fixture(scope="module")
def cut_video(tmp_path_factory) -> Path:
    """10 s: 5 s red then 5 s blue (one hard cut at 5 s), with a tone."""
    out = tmp_path_factory.mktemp("cut") / "cut.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "color=red:s=1920x1080:r=30:d=5",
                    "-f", "lavfi", "-i", "color=blue:s=1920x1080:r=30:d=5",
                    "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=10",
                    "-filter_complex", "[0:v][1:v]concat=n=2:v=1[v]", "-map", "[v]", "-map", "2:a",
                    "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", str(out)],
                   check=True)
    return out


@needs_ffmpeg
def test_detect_cut_and_centre_on_face(cut_video, tmp_path, monkeypatch):
    cuts = detect_cuts(cut_video, 1.0, 9.0)
    assert len(cuts) == 1 and cuts[0] == pytest.approx(4.0, abs=0.1)   # clip seconds
    # fake face finder: faces on the left in red shot, right in blue shot
    def fake(png):
        return (0.2, 0.05) if _is_red(png) else (0.8, 0.05)
    monkeypatch.setattr(motion, "face_center_x", fake)
    c = shot_centres(cut_video, 1.0, 9.0, tmp_path / "shots")
    assert [x for _, _, x in c] == [0.2, 0.8]


def _is_red(png: Path) -> bool:
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(png), "-vf", "scale=1:1", "-f", "rawvideo",
                        "-pix_fmt", "rgb24", "-"], capture_output=True, check=True)
    return r.stdout[0] > r.stdout[2]


@needs_ffmpeg
def test_render_with_zoom_and_tracking(source_video, cut_video, tmp_path):
    m = render_clip("z1", source_video, tmp_path / "a", 3.0, 18.0, WORDS, TEST_LAYOUT, TEST_STYLE,
                    hook_offset=3.0, zoom=Z)
    assert m["zooms"] and abs(m["duration"] - 15.0) < 0.01
    m2 = render_clip("z2", cut_video, tmp_path / "b", 1.0, 9.0, WORDS[:6], None, TEST_STYLE,
                     zoom=Z, track=True)
    assert len(m2["shots"]) == 2
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=width,height,nb_frames",
                            "-select_streams", "v", "-of", "csv=p=0", str(tmp_path / "b" / "clip.mp4")],
                           capture_output=True, text=True, check=True).stdout.strip()
    w, h, n = probe.split(",")
    assert (w, h) == ("1080", "1920") and abs(int(n) - 240) <= 2
