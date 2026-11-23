"""Dashboard editor -> worker contract (D091). The dashboard sends review_clip with
kind "trim" and payload {"edit": {...changed fields...}}; trims are clip-relative."""
from clipworker.editplan import LINE_WORDS, edit_overrides
from clipworker.render.ffmpeg import video_filter

from conftest import needs_ffmpeg
from test_pipeline import _env, _moment


def test_trim_is_shifted_into_window_seconds():
    o, title = edit_overrides({"trim_in": 1.5, "trim_out": 9}, base_in=2.0, base_out=16.0)
    assert (o["trim_in"], o["trim_out"]) == (3.5, 11.0) and title is None


def test_bad_or_short_trim_is_ignored_and_values_clamped():
    o, _ = edit_overrides({"trim_in": 5, "trim_out": 5.2, "crop_x": 7, "zoom": 0.4}, 0, 20)
    assert "trim_in" not in o and o["crop_x"] == 1.0 and o["zoom_scale"] == 1.0
    o, _ = edit_overrides({"trim_in": "x", "trim_out": None, "zoom": float("nan")}, 0, 20)
    assert o == {}


def test_untouched_fields_produce_no_overrides():
    assert edit_overrides({}, 2, 16) == ({}, None)
    assert edit_overrides({"splits": [3.0]}, 2, 16) == ({}, None)  # cuts stay note-only


def test_captions_headline_emphasis():
    o, title = edit_overrides({"caption_style": "line", "emphasis_words": ["MAP!", " ", "Spawn"],
                               "headline": "  He hit THAT  "}, 0, 20)
    assert o["words_per_line"] == LINE_WORDS and o["emphasis_words"] == ["map", "spawn"]
    assert title == "He hit THAT"
    assert edit_overrides({"caption_style": "words"}, 0, 20)[0]["words_per_line"] == 3


def test_crop_x_places_the_full_frame_window():
    g = video_filter(None, None, crop_x=0.2)
    assert "crop=ih*9/16:ih:'max(0,min(iw-ih*9/16,iw*0.2000-ih*9/32))':0" in g
    assert "crop=ih*9/16:ih," in video_filter(None, None)  # default stays centred


@needs_ffmpeg
def test_editor_revision_rerenders_and_waits_for_zo(tmp_path, source_video):
    pipe, sb, store = _env(tmp_path, source_video)
    pipe.on_moment(_moment())
    for _ in range(8):
        pipe.run_once()
    clip = sb.t["clips"][0]
    base = store.job(clip["job_id"]).data["judgment"]
    sb.human(clip["id"], "revise")
    sb.insert("revisions", {"clip_id": clip["id"], "kind": "trim", "note": "Editor: trim", "resolved_at": None,
                            "payload": {"apply_all": False, "edit": {
                                "trim_in": 1.0, "trim_out": 12.0, "crop_x": 0.25, "zoom": 1.0,
                                "caption_style": "line", "emphasis_words": ["map"],
                                "headline": "He hit THAT from spawn"}}})
    assert pipe.process_revisions() == 1
    clip = sb.t["clips"][0]
    assert clip["state"] == "pending_review" and clip["revision"] == 1   # human gate kept
    assert clip["title"] == "He hit THAT from spawn"
    assert abs(clip["duration_s"] - 11.0) < 0.1
    m = clip["manifest"]
    assert m["window"] == [base["trim_in"] + 1.0, base["trim_in"] + 12.0]
    assert m["layout"] is None and not m.get("shots")                   # manual crop, no tracking
    assert not m["zooms"]                                               # zoom 100% = off
    j = clip["judge"]
    assert j["crop_x"] == 0.25 and j["words_per_line"] == LINE_WORDS and j["emphasis_words"] == ["map"]
    ass = pipe.s.renders_dir.rglob("captions.ass")
    assert any("map" in p.read_text(encoding="utf-8").lower() for p in ass)
