import json
import shutil
from pathlib import Path

from clipworker.config import DEFAULT_REACTIONS, Channel, DetectorParams, Settings
from clipworker.links import LinkRunner, audio_moments, parse_link, pick_channel

from conftest import TEST_LAYOUT, TEST_STYLE, needs_ffmpeg
from fakes import FakeSupabase
from test_pipeline import FakeJudge, FakeTr

CASES = json.loads((Path(__file__).parents[2] / "docs" / "link_cases.json").read_text(encoding="utf-8"))


def test_link_keys_match_shared_cases():
    # same list feeds public.link_key (supabase/tests/links_test.sql) and dashboard/lib/links.ts
    for url, want in CASES:
        got = parse_link(url)
        assert (got.key if got else None) == want, url


def test_link_login_from_url():
    assert parse_link("https://www.twitch.tv/Lacy/clip/Abc-1").login == "lacy"
    assert parse_link("https://kick.com/adinross/videos/0b9a8c7d-1234-4abc-9def-0123456789ab").login == "adinross"
    assert parse_link("https://www.twitch.tv/videos/1").login is None


def _ch(key, layout=TEST_LAYOUT, name=""):
    plat, login = key.split(":")
    return Channel(key, plat, login, login, layout, DEFAULT_REACTIONS, DetectorParams(), name=name)


def test_pick_channel():
    chans = [_ch("twitch:lacy", name="Lacy"), _ch("kick:adinross", name="Adin Ross"), _ch("twitch:jynxzi")]
    vod = parse_link("https://www.twitch.tv/videos/5")
    assert pick_channel(chans, "jynxzi", vod, {}).key == "twitch:jynxzi"            # zo's pick wins
    assert pick_channel(chans, None, vod, {"uploader_id": "Lacy"}).key == "twitch:lacy"
    yt = parse_link("https://youtu.be/dQw4w9WgXcQ")
    assert pick_channel(chans, None, yt, {"uploader_id": "@AdinRoss"}).key == "kick:adinross"
    assert pick_channel(chans, None, yt, {"uploader": "Someone Else"}) is None


def test_audio_moments_find_spikes_apart():
    loud = [(i * 0.5, -30.0 + (i % 3) * 0.3) for i in range(1200)]            # 10 min, steady
    for t0 in (200.0, 210.0, 420.0):                                           # 2 spikes 10 s apart + 1
        for i in range(10):
            idx = int((t0 + i * 0.5) / 0.5)
            loud[idx] = (loud[idx][0], -12.0)
    ms = audio_moments(loud, "twitch:lacy", 600.0, 25.0, 15.0, max_n=5)
    assert len(ms) == 2                                                        # 200/210 merged by the gap
    assert abs(ms[0].peak_ts - 204) < 8 and abs(ms[1].peak_ts - 424) < 8
    assert ms[0].window_start == ms[0].peak_ts - 25 and ms[0].features["z_audio"] >= 2
    assert audio_moments([], "k", 10, 1, 1, 3) == []


class FakeFetch:
    def __init__(self, video, info, chat=None):
        self.v, self.info, self.c, self.calls = video, info, chat, []

    def probe(self, url):
        return self.info

    def video(self, url, out_dir, start, end):
        self.calls.append((start, end))
        out_dir.mkdir(parents=True, exist_ok=True)
        dst = out_dir / "source.mp4"
        shutil.copy(self.v, dst)
        return dst

    def chat(self, ref, out_dir):
        return self.c


def _runner(tmp_path, video, info, loud, full_frame=False, chans=None, judge=None, **row):
    sb = FakeSupabase()
    sb.t["link_jobs"] = []
    sb.insert("streamers", {"id": "s-lacy", "slug": "lacy"})
    chans = chans or [_ch("twitch:lacy")]
    s = Settings(work_dir=tmp_path, channels=chans, caption_style=TEST_STYLE)
    sb.insert("link_jobs", {"id": "L1", "url": row.pop("url", "https://www.twitch.tv/videos/77"),
                            "status": "queued", "streamer": row.pop("streamer", None), "start_s": None,
                            "end_s": None, "max_clips": 3, "full_frame": full_frame, "requested_at": "1", **row})
    seen = {}

    def render(*a, **kw):  # records the layout the clip was cut with, then uses the real renderer
        from clipworker.render.ffmpeg import render_clip
        seen["layout"], seen["track"] = a[6], kw.get("track")
        return render_clip(*a, **kw)

    r = LinkRunner(s, sb, FakeTr(), judge or FakeJudge(), FakeFetch(video, info), clock=lambda: 2_000_000_000.0,
                   loudness=lambda v: loud, pipeline_kw={"render": render})
    return r, sb, seen


@needs_ffmpeg
def test_short_link_lands_in_review(tmp_path, source_video):
    """30 s X/Twitch clip: one whole-video moment, kept (zo picked it), real render + QA -> pending_review."""
    loud = [(i * 0.5, -25.0) for i in range(60)]
    info = {"duration": 30, "title": "lacy moment", "uploader_id": "lacy", "timestamp": 1_900_000_000}
    r, sb, seen = _runner(tmp_path, source_video, info, loud)
    assert r.run_once() == 1
    row = sb.t["link_jobs"][0]
    assert row["status"] == "done", row.get("detail")
    assert row["clips"] == 1 and row["streamer"] == "lacy" and row["cost_usd"] == 0.001
    clip = sb.t["clips"][0]
    assert clip["state"] == "pending_review" and clip["channel_key"] == "twitch:lacy"
    assert clip["moment_at"].startswith("2030-03-17")              # real source clock, not 1970
    assert seen["layout"] is TEST_LAYOUT and not seen["track"]
    assert not sb.t["publications"]                                 # nothing posts


@needs_ffmpeg
def test_full_frame_link_uses_tracked_full_frame(tmp_path, source_video):
    loud = [(i * 0.5, -25.0) for i in range(60)]
    r, sb, seen = _runner(tmp_path, source_video, {"duration": 30, "uploader_id": "lacy"}, loud, full_frame=True)
    r.run_once()
    assert sb.t["link_jobs"][0]["status"] == "done"
    assert seen["layout"] is None and seen["track"] is True          # IRL path (render/ face tracking)


def test_failures_are_shown(tmp_path):
    loud = []
    r, sb, _ = _runner(tmp_path, Path("x"), {"is_live": True}, loud)
    r.run_once()
    row = sb.t["link_jobs"][0]
    assert row["status"] == "failed" and "still live" in row["detail"]

    r, sb, _ = _runner(tmp_path, Path("x"), {"duration": 100, "uploader": "Random Guy"}, loud,
                       url="https://youtu.be/dQw4w9WgXcQ")
    r.run_once()
    row = sb.t["link_jobs"][0]
    assert row["status"] == "failed" and "not on the roster" in row["detail"]

    r, sb, _ = _runner(tmp_path, Path("x"), {"duration": 9 * 3600, "uploader_id": "lacy"}, loud)
    r.run_once()
    assert "8 hours" in sb.t["link_jobs"][0]["detail"]


def test_canceled_link_stops(tmp_path):
    r, sb, _ = _runner(tmp_path, Path("x"), {"duration": 100, "uploader_id": "lacy"}, [])

    def video(url, out_dir, start, end):
        sb.t["link_jobs"][0]["status"] = "canceled"   # zo pressed Cancel during the download
        return Path("x")
    r.fetch.video = video
    r.run_once()
    row = sb.t["link_jobs"][0]
    assert row["status"] == "canceled" and not sb.t["clips"]


def test_moments_already_clipped_live_are_skipped(tmp_path):
    (tmp_path / "v.mp4").write_bytes(b"")
    t0 = 1_900_000_000
    loud = [(i * 0.5, -30.0) for i in range(1200)]
    for i in range(10):
        loud[400 + i] = (loud[400 + i][0], -10.0)                                 # spike at ~200 s
    r, sb, _ = _runner(tmp_path, tmp_path / "v.mp4", {"duration": 600, "uploader_id": "lacy", "timestamp": t0}, loud)
    from clipworker.links import iso
    sb.insert("clips", {"id": "c0", "job_id": "live1", "channel_key": "twitch:lacy", "state": "pending_review",
                        "moment_at": iso(t0 + 203)})
    r.run_once()
    row = sb.t["link_jobs"][0]
    assert row["status"] == "done" and row["candidates"] == 1
    assert "already clipped live" in row["detail"]
