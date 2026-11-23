import json
import subprocess

from conftest import needs_ffmpeg

from clipworker.render import tools as T


def probe(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(p)],
                       check=True, capture_output=True, text=True)
    d = json.loads(r.stdout)
    v = next(s for s in d["streams"] if s["codec_type"] == "video")
    return float(d["format"]["duration"]), v["width"], v["height"], any(s["codec_type"] == "audio" for s in d["streams"])


def make_clip(path, dur=6):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                    "-i", f"testsrc2=s=1080x1920:r=30:d={dur}", "-f", "lavfi",
                    "-i", f"sine=f=440:d={dur}:sample_rate=48000", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-shortest", str(path)], check=True)


def test_commands_never_scale_or_crop():
    cmd, _ = T.slowmo_vignette_command("a.mp4", "b.mp4", 6, 2)
    g = " ".join(cmd)
    assert "scale=" not in g and "crop=" not in g and "zoompan" not in g and "vignette" in g


def test_atempo_chains_below_half():
    assert T._atempo(0.5) == "atempo=0.500"
    assert T._atempo(0.25).count("atempo") == 2


@needs_ffmpeg
def test_slowmo_vignette_stretches_only_the_window(tmp_path):
    src, out = tmp_path / "c.mp4", tmp_path / "o.mp4"
    make_clip(src, 6)
    cmd, new_dur = T.slowmo_vignette_command(src, out, 6.0, 2.0, 1.0, 0.5)
    subprocess.run(cmd, check=True)
    d, w, h, audio = probe(out)
    assert (w, h) == (1080, 1920) and audio
    assert abs(new_dur - 7.0) < 0.01 and abs(d - 7.0) < 0.25


@needs_ffmpeg
def test_black_spacer_adds_length(tmp_path):
    src, out = tmp_path / "c.mp4", tmp_path / "o.mp4"
    make_clip(src, 4)
    cmd, new_dur = T.black_spacer_command(src, out, 4.0, 2.0, 0.4)
    subprocess.run(cmd, check=True)
    d, w, h, audio = probe(out)
    assert (w, h) == (1080, 1920) and audio and abs(d - 4.4) < 0.25 and abs(new_dur - 4.4) < 0.01


@needs_ffmpeg
def test_music_cue_keeps_video_and_length(tmp_path):
    src, out, music = tmp_path / "c.mp4", tmp_path / "o.mp4", tmp_path / "m.wav"
    make_clip(src, 4)
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    "sine=f=220:d=1:sample_rate=48000", str(music)], check=True)  # shorter than the clip: looped
    subprocess.run(T.music_cue_command(src, out, music, 0.5), check=True)
    d, w, h, audio = probe(out)
    assert (w, h) == (1080, 1920) and audio and abs(d - 4.0) < 0.25


@needs_ffmpeg
def test_apply_effects_chain_and_skips(tmp_path):
    clip = tmp_path / "clip.mp4"
    make_clip(clip, 6)
    dur = T.apply_effects(clip, [
        {"tool": "slowmo_vignette", "at": 3.0, "length": 1.0},
        {"tool": "black_spacer", "at": 1.0, "length": 0.3},
        {"tool": "music_cue"},          # no file: skipped, not fatal
        {"tool": "sfx_hit"},            # not an after-render effect: skipped
    ], 6.0)
    d = probe(clip)[0]
    assert abs(dur - 7.3) < 0.01 and abs(d - 7.3) < 0.3
    assert not list(tmp_path.glob("*.fx.mp4"))
