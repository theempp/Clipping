"""Caption over an existing render (clip footage gone): timed, >= 60 px, never re-cuts."""
import subprocess
from dataclasses import replace

from clipworker.render.overlay import Overlay, build_overlay_ass, parse_overlay

from conftest import TEST_STYLE, needs_ffmpeg
from test_pipeline import _env


def test_parse_overlay_validates_and_caps():
    assert parse_overlay({"overlay": {"text": "  his dad   shot him ", "end_s": 2.5}}) == Overlay("HIS DAD SHOT HIM", 0.0, 2.5)
    assert parse_overlay({"overlay": {"text": "x", "start_s": 0, "end_s": 99}}).end_s == 10.0
    assert parse_overlay({"overlay": {"text": "", "end_s": 2}}) is None
    assert parse_overlay({"overlay": {"text": "x", "start_s": 2, "end_s": 2.2}}) is None
    assert parse_overlay({"edit": {"headline": "x"}}) is None
    assert parse_overlay(None) is None


def test_overlay_ass_is_timed_top_and_at_least_60px():
    ass = build_overlay_ass(Overlay("HIS DAD SHOT HIM", 0.0, 2.5), replace(TEST_STYLE, size=40))
    style = next(l for l in ass.splitlines() if l.startswith("Style: Head"))
    assert style.split(",")[2] == "60"                       # D114 floor
    assert ",8," in style                                    # top-centre alignment
    assert "Dialogue: 1,0:00:00.00,0:00:02.50,Head" in ass   # drops off at 2.5 s


@needs_ffmpeg
def test_overlay_revision_without_local_job(tmp_path, source_video):
    pipe, sb, store = _env(tmp_path, source_video)
    clip_mp4 = tmp_path / "render.mp4"   # a 9:16 render already in storage
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=1080x1920:rate=30:duration=4",
                    "-f", "lavfi", "-i", "sine=duration=4", "-c:v", "libx264", "-preset", "ultrafast",
                    "-c:a", "aac", "-shortest", str(clip_mp4)], check=True)
    sb.uploads["lacy/old/clip.mp4"] = clip_mp4.read_bytes()
    sb.insert("clips", {"id": "c1", "job_id": "gone-job", "state": "revise", "storage_path": "lacy/old/clip.mp4",
                        "thumb_path": "lacy/old/thumb.jpg", "revision": 1, "manifest": {"video": "x"}})
    sb.insert("revisions", {"clip_id": "c1", "kind": "caption", "note": "caption", "resolved_at": None,
                            "payload": {"overlay": {"text": "His dad shot him so he clipped it", "end_s": 2.5}}})
    before = sb.uploads["lacy/old/clip.mp4"]
    assert pipe.process_revisions() == 1
    c = sb.t["clips"][0]
    assert c["state"] == "pending_review" and c["revision"] == 2
    assert c["manifest"]["overlay"] == {"text": "HIS DAD SHOT HIM SO HE CLIPPED IT", "start_s": 0.0, "end_s": 2.5, "revision": 2}
    assert c["manifest"]["video"] == "x"                     # rest of the manifest kept
    assert sb.uploads["lacy/old/clip.mp4"] != before          # new render uploaded over the same path
    assert all(r["resolved_at"] for r in sb.t["revisions"])
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                str(tmp_path / "overlays" / "c1-r2" / "clip_overlay.mp4")],
                               capture_output=True, text=True, check=True).stdout)
    assert abs(dur - 4.0) < 0.2                               # never re-cut


def test_overlay_failure_is_flagged_not_retried(tmp_path, source_video):
    pipe, sb, store = _env(tmp_path, source_video)
    sb.insert("clips", {"id": "c1", "job_id": "gone", "state": "revise", "storage_path": "missing/clip.mp4", "revision": 0})
    sb.insert("revisions", {"clip_id": "c1", "kind": "caption", "note": "c", "resolved_at": None,
                            "payload": {"overlay": {"text": "hi", "end_s": 2}}})
    assert pipe.process_revisions() == 0
    c = sb.t["clips"][0]
    assert c["state"] == "revise" and "caption overlay failed" in c["revise_failed"]["reason"]
    assert pipe.process_revisions() == 0                     # same note is not retried in a loop
