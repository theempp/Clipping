from pathlib import Path

from clipworker.qa import MAX_BYTES
from clipworker.render.ffmpeg import AUDIO_KBPS, cut_command, rate_cap, render_command
from clipworker.render.tools import enc, stinger_command


def _kbps(args):
    return int(args[args.index("-maxrate") + 1].rstrip("k"))


def test_short_clip_keeps_d118_ceiling():
    assert _kbps(rate_cap(20)) == 16000
    assert _kbps(rate_cap(None)) == 16000


def test_long_clip_fits_storage_cap():
    for dur in (30, 45, 57.2, 60, 75):
        worst = (_kbps(rate_cap(dur)) + AUDIO_KBPS) * 1000 / 8 * dur
        assert worst < MAX_BYTES * 0.92, dur


def test_every_encode_site_is_capped():
    p = Path("x.mp4")
    assert _kbps(render_command(p, p, 0, 60, None, None, 30)) < 6500
    assert _kbps(cut_command(p, p, [(10, 20)], 70)) < 6500   # 60 s kept
    assert _kbps(enc(60)) < 6500
    assert _kbps(stinger_command(p, p, p, 1, 1, dur=60)) < 6500
