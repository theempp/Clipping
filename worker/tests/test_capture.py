import datetime as dt
import subprocess

from clipworker.capture.buffer import (capture_commands, covering, extract_window, list_segments,
                                       parse_ebur128, prune)

from conftest import needs_ffmpeg

UTC = dt.timezone.utc


def _seg_name(ts: float) -> str:
    return dt.datetime.fromtimestamp(ts, UTC).strftime("%Y%m%d-%H%M%S") + ".ts"


def test_capture_commands_shape(tmp_path):
    sl, ff = capture_commands("twitch", "lacy", tmp_path)
    assert sl[-2:] == ["https://twitch.tv/lacy", "best"]
    assert "segment" in ff and "ebur128=peak=none" in ff
    sl, _ = capture_commands("kick", "silky", tmp_path)
    assert "--twitch-disable-ads" not in sl and "https://kick.com/silky" in sl


def test_parse_ebur128_downsamples():
    lines = ["[Parsed_ebur128_0 @ 0x1] t: 0.1  TARGET:-23 LUFS    M: -30.2 S:-120.7 I: -30.2 LUFS",
             "[Parsed_ebur128_0 @ 0x1] t: 0.9  TARGET:-23 LUFS    M: -28.0 S:-120.7 I: -29 LUFS",
             "[Parsed_ebur128_0 @ 0x1] t: 1.2  TARGET:-23 LUFS    M: -inf S:-120.7 I: -29 LUFS",
             "garbage"]
    assert parse_ebur128(lines, 1000.0) == [(1000.0, -28.0), (1001.0, -120.0)]


def test_segments_cover_and_prune(tmp_path):
    base = 1_700_000_000.0
    for i in range(70):
        (tmp_path / _seg_name(base + i * 10)).write_bytes(b"x")
    segs = list_segments(tmp_path, tz=UTC)
    assert len(segs) == 70 and segs[0].start_ts == base
    cov = covering(segs, base + 95, base + 135)
    assert [s.start_ts - base for s in cov] == [90, 100, 110, 120, 130]
    removed = prune(tmp_path, now=base + 700, keep_s=600, tz=UTC)
    assert removed == 9
    assert len(list_segments(tmp_path, tz=UTC)) == 61


@needs_ffmpeg
def test_extract_window_real_ffmpeg(tmp_path):
    buf = tmp_path / "buf"
    buf.mkdir()
    base = 1_700_000_000.0
    for i in range(4):
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                        "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30:duration=10",
                        "-f", "lavfi", "-i", "sine=frequency=300:duration=10",
                        "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest",
                        "-f", "mpegts", str(buf / _seg_name(base + i * 10))], check=True)
    out = extract_window(buf, base + 5, base + 25, tmp_path / "w", tz=UTC)
    assert not out["partial"]
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                        "default=nw=1:nk=1", out["video"]], capture_output=True, text=True, check=True)
    assert abs(float(r.stdout) - 20.0) < 0.5
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=sample_rate,channels", "-of",
                        "csv=p=0", out["audio"]], capture_output=True, text=True, check=True)
    assert r.stdout.strip() == "16000,1"
