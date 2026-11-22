from clipworker import rules


def test_zoo_notes_from_zo_become_smooth_camera_rule():
    for note in ["Yeah I've already noticed that zooming in and out is very sharp and has a very hard stop "
                 "when transitioning. Fix that. Make it way smoother with camera transitions and movements",
                 "Fix the heavy zoom in and zoom outs onto his face. Make these effects way smoother"]:
        assert rules.parse_note(note) == {"zoom_style": "smooth"}
    assert rules.parse_note("no zooms at all please") == {"zoom": False}


def test_other_notes():
    assert rules.parse_note("remove the sound effects") == {"sfx": False}
    assert rules.parse_note("make the captions blue") == {"caption_colour": "#2F80FF"}
    assert rules.parse_note("keep it under 30 seconds") == {"max_len_s": 30.0}
    assert rules.parse_note("is the gta clip from the actual stream?") == {}


def test_standing_and_merge():
    assert rules.standing({"title": "x", "zoom_style": "smooth", "best_part_only": True}) == {"zoom_style": "smooth"}
    rows = [{"key": "zoom", "value": False, "active": True}, {"key": "zoom_style", "value": "smooth", "active": True},
            {"key": "zoom", "value": True, "active": True}, {"key": "sfx", "value": False, "active": False}]
    assert rules.merge(rows) == {"zoom": False}   # newest zoom wins; off beats style; inactive ignored


def test_breaks():
    old = {"manifest": {"zooms": [2.0], "sfx": False, "motion": {}}, "judge": {}, "duration_s": 40}
    new = {"manifest": {"zooms": [2.0], "motion": {"motion_version": 2}}, "judge": {}, "duration_s": 20}
    s = {"zoom_style": "smooth", "max_len_s": 30.0}
    assert rules.breaks(old, s, 2) == ["zoom_style", "max_len_s"]
    assert rules.breaks(new, s, 2) == []
    assert rules.breaks(new, {"zoom": False}, 2) == ["zoom"]
    applied = {**old, "judge": {"max_len_s": 30.0, "zoom_style": "smooth"}}
    assert rules.breaks(applied, s, 2) == []          # already rendered with both rules: no loop
    assert rules.label("zoom_style", "smooth").startswith("Smooth camera")
