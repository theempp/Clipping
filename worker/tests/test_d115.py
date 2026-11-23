"""D115: GTA stingers (baked overlays) and continuous IRL face tracking (MediaPipe)."""
import dataclasses
import json
import os
import random
import subprocess
from pathlib import Path

import pytest

from clipworker.pipeline import is_irl
from clipworker.render import motion, recipe, stingers
from clipworker.render import tools as T

from conftest import needs_ffmpeg
from test_motion import cut_video  # noqa: F401  (fixture)
from test_pipeline import _env, _moment


def probe(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(p)],
                       check=True, capture_output=True, text=True)
    d = json.loads(r.stdout)
    v = next(s for s in d["streams"] if s["codec_type"] == "video")
    return float(d["format"]["duration"]), v["width"], v["height"]


# ---- face path ----

def _samples(fn, dur=8.0, fps=motion.TRACK_FPS):
    return [(round(i / fps, 3), fn(i / fps)) for i in range(int(dur * fps))]


def test_still_face_keeps_camera_still():
    keys = motion.face_path(_samples(lambda t: 0.62 + (0.01 if int(t * 4) % 2 else -0.01)), [], 8.0)
    assert len(keys) == 2 and keys[0][1] == keys[1][1]


def test_walking_face_pans_smoothly_and_capped():
    keys = motion.face_path(_samples(lambda t: 0.25 + 0.06 * t), [], 8.0)  # walks 0.25 -> 0.67
    xs = [x for _, x, _ in keys]
    assert xs == sorted(xs) and xs[-1] > 0.5
    for (t0, x0, _), (t1, x1, _) in zip(keys, keys[1:]):
        if t1 > t0:
            assert (x1 - x0) / (t1 - t0) <= motion.MAX_PAN_PER_S + 1e-6


def test_cut_jumps_and_missing_faces_hold():
    keys = motion.face_path(_samples(lambda t: 0.2 if t < 4 else (None if t < 5 else 0.8)), [4.0], 8.0)
    jumps = [k for k in keys if k[2]]
    assert len(jumps) == 1 and jumps[0][0] == 4.0 and jumps[0][1] == pytest.approx(0.8, abs=0.06)
    assert all(not k[2] for k in keys if k[0] < 4.0)


def test_busy_path_is_capped():
    rng = random.Random(1)
    keys = motion.face_path(_samples(lambda t: rng.random(), dur=30.0), [5.0 * i for i in range(1, 6)], 30.0)
    assert len(keys) <= motion.MAX_KEYS


def test_path_crop_never_zooms():
    f = motion.path_crop_filter([(0.0, 0.3, False), (2.0, 0.5, False), (4.0, 0.8, True)])
    assert f.startswith("crop=ih*9/16:ih:") and "zoompan" not in f and "scale" not in f


@needs_ffmpeg
def test_track_render_follows_face(cut_video, tmp_path, monkeypatch):
    from clipworker.render.ffmpeg import render_clip
    from conftest import TEST_STYLE
    from test_motion import WORDS, _is_red
    monkeypatch.setattr(motion, "_mediapipe", lambda: None)
    monkeypatch.setattr(motion, "face_center_x", lambda png: (0.2, 0.05) if _is_red(png) else (0.8, 0.05))
    m = render_clip("t1", cut_video, tmp_path / "b", 1.0, 9.0, WORDS[:6], None, TEST_STYLE, track=True)
    assert m["reframe"] == "haar" and [x for *_, x in m["shots"]] == [0.2, 0.8]
    assert any(k[2] for k in m["track_keys"]) and m["zooms"] == []
    _, w, h = probe(tmp_path / "b" / "clip.mp4")
    assert (w, h) == (1080, 1920)


def test_face_model_hash_is_checked(tmp_path):
    class R:
        def __init__(self, b): self.b = b
        def read(self): return self.b
        def __enter__(self): return self
        def __exit__(self, *a): return False
    p = tmp_path / "m.tflite"
    with pytest.raises(RuntimeError):
        motion.ensure_face_model(p, urlopen=lambda url, timeout: R(b"not the model"))
    assert not p.exists()


def test_mediapipe_finds_a_face_when_installed(monkeypatch):
    pytest.importorskip("mediapipe")
    model = Path(os.environ.get(motion.FACE_MODEL_ENV, "/nonexistent"))
    frame = Path(os.environ.get("CLIPP_TEST_FACE_FRAME", "/nonexistent"))
    if not model.exists() or not frame.exists():
        pytest.skip("set CLIPP_FACE_MODEL and CLIPP_TEST_FACE_FRAME to run")
    monkeypatch.setattr(motion, "_mp_detector", None)
    monkeypatch.setattr(motion, "_mp_failed", False)
    assert motion.detector_name() == "mediapipe"
    hit = motion.detect_face(frame)
    assert hit is not None and 0 < hit[0] < 1


# ---- IRL category ----

def test_is_irl():
    assert is_irl("Just Chatting") and is_irl("irl") and not is_irl("Grand Theft Auto VI") and not is_irl(None)
    assert is_irl("Chess", ["Chess"]) and not is_irl("IRL", [])


# ---- stingers ----

def test_stinger_tool_only_on_gta6():
    assert "gta6_sting" not in recipe.moment_tags({"category": "fail"})
    assert "gta6_sting" in recipe.moment_tags({"category": "fail", "gta6": True})
    assert "gta6_sting" not in recipe.moment_tags({"category": "wholesome", "gta6": True})
    sw = recipe.StreamerWeights()
    assert "gta_stinger" not in recipe._eligible(sw, {"punchline"})
    assert "gta_stinger" in recipe._eligible(sw, {"gta6_sting"})


def test_stinger_catalogue_has_no_zoom_and_every_fit_category_has_one():
    assert not any("zoom" in s.name or "zoom" in s.component for s in stingers.STINGS.values())
    for cat in ("fail", "rage", "clutch", "funny"):
        assert stingers.fits(cat)


def test_stinger_choose_needs_a_baked_file(tmp_path):
    rng = random.Random(0)
    assert stingers.choose("fail", rng, None) is None
    assert stingers.choose("fail", rng, tmp_path) is None
    stingers.asset_path(tmp_path, stingers.STINGS["wasted"]).write_bytes(b"x")
    assert stingers.choose("fail", rng, tmp_path).name == "wasted"
    assert stingers.choose("clutch", rng, tmp_path) is None


def test_stinger_placement():
    assert stingers.placement(6.0, 20.0, 5.0) == (6.0, 5.0)
    assert stingers.placement(18.0, 20.0, 5.0) == (18.0, 2.0)
    assert stingers.placement(-1.0, 20.0, 5.0) == (0.0, 5.0)


@needs_ffmpeg
def test_stinger_overlay_keeps_clip(tmp_path):
    from test_tools import make_clip
    clip = tmp_path / "c.mp4"
    make_clip(clip, 6)
    sting = tmp_path / "s.mov"  # a half-transparent red box, ProRes 4444 like the real bakes
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                    "-i", "color=c=red@0.5:s=1080x1920:r=30:d=2,format=yuva444p10le",
                    "-c:v", "prores_ks", "-profile:v", "4444", str(sting)], check=True)
    cmd = T.stinger_command(clip, tmp_path / "o.mp4", sting, 2.0, 2.0, mono=True)
    assert "crop=" not in " ".join(cmd) and "zoompan" not in " ".join(cmd)
    T.apply_effects(clip, [{"tool": "gta_stinger", "at": 2.0, "length": 2.0, "mono": True, "file": str(sting)}], 6.0)
    d, w, h = probe(clip)
    assert abs(d - 6.0) < 0.1 and (w, h) == (1080, 1920)
    T.apply_effects(clip, [{"tool": "gta_stinger", "at": 1.0, "length": 1.0, "file": str(tmp_path / "no.mov")}], 6.0)


# ---- pipeline ----

@needs_ffmpeg
def test_irl_stream_renders_full_frame_tracked(tmp_path, source_video, monkeypatch):
    monkeypatch.setattr(motion, "_mediapipe", lambda: None)
    pipe, sb, store = _env(tmp_path, source_video)
    pipe.s = dataclasses.replace(pipe.s, extra={"recipe_weights": str(tmp_path / "w.json")})
    m = _moment()
    m.features["game"] = "Just Chatting"
    job = pipe.on_moment(m)
    for _ in range(8):
        pipe.run_once()
    j = store.job(job)
    man = j.data["manifest"]
    assert man["layout"] is None and man["track_keys"] and man["recipe"]["layout"] == "track"
    assert not {"swap_full_face", "swap_full_game"} & set(man["recipe"]["tools"])
    assert j.data["judgment"]["layout_mode"] == "track" and j.data["judgment"]["gta6"] is False


@needs_ffmpeg
def test_gta6_clip_gets_baked_stinger(tmp_path, source_video):
    pipe, sb, store = _env(tmp_path, source_video)
    sdir = tmp_path / "stingers"
    sdir.mkdir()
    for s in stingers.fits("clutch"):  # FakeJudge says clutch
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                        "-i", "color=c=white@0.4:s=1080x1920:r=30:d=2,format=yuva444p10le",
                        "-c:v", "prores_ks", "-profile:v", "4444", str(stingers.asset_path(sdir, s))], check=True)
    pipe.s = dataclasses.replace(pipe.s, extra={"recipe_weights": str(tmp_path / "w.json"), "stinger_dir": str(sdir)})
    m = _moment()
    m.features["game"] = "Grand Theft Auto VI"
    job = pipe.on_moment(m)
    for _ in range(8):
        pipe.run_once()
    j = store.job(job)
    assert j.data["judgment"]["gta6"] is True
    rec = j.data["judgment"]["recipe"]
    rec["tools"] = ["hard_cut", "headline_box", "gta_stinger"]  # as if the picker chose it
    store.patch_data(job, {"judgment": {**j.data["judgment"], "recipe": rec}})
    clip = sb.t["clips"][0]
    sb.human(clip["id"], "revise")
    sb.insert("revisions", {"clip_id": clip["id"], "kind": "title", "note": "t",
                            "payload": {"title": "x"}, "resolved_at": None})
    assert pipe.process_revisions() == 1
    man = store.job(job).data["manifest"]
    assert man["stinger"] and man["stinger"]["name"] in {s.name for s in stingers.fits("clutch")}
    assert man["recipe_problems"] == []
