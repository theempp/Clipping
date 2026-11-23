import random

import pytest

from clipworker.render import recipe as R


def mk(**kw):
    base = dict(clip_id="c1", streamer="lacy", tools=["hard_cut", "headline_box", "slowmo_vignette"], length_s=18)
    base.update(kw)
    return R.Recipe(**base)


def test_valid_recipe_passes():
    assert R.validate(mk(), font_px=64, flashes_per_s=2) == []


def test_zoom_is_banned_d112():
    p = R.validate(mk(tools=["hard_cut", "headline_box", "zoom"]))
    assert any("D112" in x for x in p)


def test_length_bounds_and_longform_exception():
    assert R.validate(mk(length_s=8))
    assert R.validate(mk(length_s=45))
    assert R.validate(mk(length_s=45, longform=True)) == []


def test_flashback_needs_zo_approval_d113():
    fb = R.Flashback(reason="same bit last week", source_moment="vod 1:02:10")
    assert any("approved" in x for x in R.validate(mk(flashback=fb)))
    fb.approved = True
    assert R.validate(mk(flashback=fb)) == []


def test_qa_limits():
    assert R.validate(mk(), font_px=40)
    assert R.validate(mk(), flashes_per_s=4)


def test_max_three_sfx_and_transitions():
    tools = ["hard_cut", "headline_box", "sfx_hit", "sfx_whoosh", "sfx_glitch", "black_spacer"]
    assert any("SFX/transitions" in x for x in R.validate(mk(tools=tools)))


def test_to_judgment_never_zooms():
    j = R.to_judgment(mk(caption_style="headline+words", tools=["hard_cut", "headline_box", "sfx_hit"]))
    assert j == {"zoom": False, "sfx": True, "words_per_line": 3}
    assert R.to_judgment(mk())["zoom"] is False


def test_pick_fits_moment_and_never_banned():
    sw = R.StreamerWeights()
    for seed in range(30):
        tools, _ = R.pick_tools(sw, {"punchline"}, random.Random(seed), explore=False)
        assert R.validate(mk(tools=tools)) == []
        assert not set(tools) & R.BANNED
        assert "music_cue" not in tools and "black_spacer" not in tools  # not eligible for this moment


def test_pick_never_repeats_last_combo():
    sw = R.StreamerWeights()
    tags = {"punchline", "reveal", "mock_serious", "layout_swap"}
    rng = random.Random(1)
    prev = None
    for _ in range(40):
        tools, _ = R.pick_tools(sw, tags, rng, explore=False)
        assert sorted(tools) != prev
        R.record_pick(sw, tools)
        prev = sorted(tools)


def test_banned_tool_not_picked():
    sw = R.StreamerWeights(banned={"slowmo_vignette"})
    for seed in range(30):
        tools, _ = R.pick_tools(sw, {"punchline"}, random.Random(seed), explore=False)
        assert "slowmo_vignette" not in tools


def test_every_fourth_clip_explores():
    sw = R.StreamerWeights(clips_made=3)
    _, explored = R.pick_tools(sw, {"punchline"}, random.Random(0))
    assert explored
    sw.clips_made = 0
    assert not R.pick_tools(sw, {"punchline"}, random.Random(0))[1]


def test_explore_favours_low_weight_tools():
    sw = R.StreamerWeights(weights={"slowmo_vignette": 3.0, "sfx_hit": 0.2})
    hits = {"explore": 0, "exploit": 0}
    for seed in range(300):
        t, _ = R.pick_tools(sw, {"punchline"}, random.Random(seed), explore=True)
        hits["explore"] += "sfx_hit" in t
        t, _ = R.pick_tools(sw, {"punchline"}, random.Random(seed), explore=False)
        hits["exploit"] += "sfx_hit" in t
    assert hits["explore"] > hits["exploit"]


def test_feedback_moves_weights_and_bans_after_two_notes():
    sw = R.StreamerWeights()
    tools = ["hard_cut", "headline_box", "sfx_hit"]
    R.apply_feedback(sw, tools, "approved_clean")
    assert sw.weight("sfx_hit") > 1.0 and "hard_cut" not in sw.weights
    R.apply_feedback(sw, tools, "rejected")
    R.apply_feedback(sw, tools, "manual_edit", removed=["sfx_hit"])
    assert sw.weight("sfx_hit") < 1.0
    R.apply_feedback(sw, tools, "approved_with_note", bad_tool="sfx_hit")
    assert "sfx_hit" not in sw.banned
    R.apply_feedback(sw, tools, "approved_with_note", bad_tool="sfx_hit")
    assert "sfx_hit" in sw.banned
    with pytest.raises(ValueError):
        R.apply_feedback(sw, tools, "nonsense")


def test_weights_stay_in_range():
    sw = R.StreamerWeights()
    for _ in range(100):
        R.apply_feedback(sw, ["sfx_hit"], "approved_clean")
    assert sw.weight("sfx_hit") == R.HI
    for _ in range(100):
        R.apply_feedback(sw, ["sfx_hit"], "rejected")
    assert sw.weight("sfx_hit") == R.LO


def test_store_roundtrip(tmp_path):
    p = tmp_path / "w.json"
    st = R.WeightStore(p)
    sw = st.get("lacy")
    R.apply_feedback(sw, ["sfx_hit"], "approved_clean")
    R.record_pick(sw, ["hard_cut", "sfx_hit"])
    st.data["lacy"].banned.add("sfx_glitch")
    st.save()
    again = R.WeightStore(p).get("lacy")
    assert again.weights == sw.weights and again.banned == {"sfx_glitch"}
    assert again.last_combo == ["hard_cut", "sfx_hit"] and again.clips_made == 1


def test_recipe_json_roundtrip():
    r = mk(flashback=R.Flashback("why", "vod 1:00", approved=True))
    assert R.Recipe.from_json(r.to_json()) == r


def test_moment_tags_from_judgment():
    assert "punchline" in R.moment_tags({"category": "funny"})
    assert R.moment_tags({"category": "other", "hook_type": "none"}) == set()
    assert {"tense", "mock_serious"} <= R.moment_tags({"category": "drama"})
    assert "compilation" in R.moment_tags({"compilation": True})


def test_build_recipe_is_valid_and_deterministic_per_clip():
    sw = R.StreamerWeights()
    a = R.build_recipe("c9", "lacy", {"category": "funny"}, sw, random.Random("c9"), 16.0)
    b = R.build_recipe("c9", "lacy", {"category": "funny"}, R.StreamerWeights(), random.Random("c9"), 16.0)
    assert a == b and R.validate(a) == []
    assert a.tools[:2] == ["hard_cut", "headline_box"]
