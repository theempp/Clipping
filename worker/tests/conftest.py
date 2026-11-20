import random
import shutil
import subprocess
from pathlib import Path

import pytest

from clipworker.config import CaptionStyle, Crop, Layout

HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
needs_ffmpeg = pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg not installed")

# Test-only style. Real values come from references/ (D022); never copy these into config.
TEST_STYLE = CaptionStyle(font="DejaVu Sans", size=72, primary_colour="&H00FFFFFF",
                          highlight_colour="&H0000FFFF", outline_colour="&H00000000",
                          outline=4, margin_v=420, words_per_line=3)
TEST_LAYOUT = Layout(Crop(0, 0, 480, 270), Crop(420, 0, 1080, 1080), 640)


def synth_chat(seed=1, minutes=12, base_rate=1.0, spikes=(), users=300):
    """Quiet chat + spikes [(t_start, duration, rate, text)] -> [(ts, user, text)]."""
    rng = random.Random(seed)
    out = []
    t = 0.0
    while t < minutes * 60:
        t += rng.expovariate(base_rate)
        out.append((t, f"u{rng.randrange(users)}", rng.choice(["hi", "nice", "lol", "gg", "what"])))
    for start, dur, rate, text in spikes:
        n = int(dur * rate)
        for i in range(n):
            out.append((start + dur * i / n, f"s{rng.randrange(users * 3)}", text))
    out.sort()
    return out


@pytest.fixture(scope="session")
def source_video(tmp_path_factory) -> Path:
    """30 s 1920x1080@30 test pattern with a tone."""
    d = tmp_path_factory.mktemp("src")
    out = d / "window.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=30:duration=30",
                    "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=30",
                    "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", str(out)],
                   check=True)
    return out
