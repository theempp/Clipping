"""Roster groups, GTA 6 filter/boost and the capture cap (D069)."""
import tomllib
from pathlib import Path

import pytest

from clipworker.config import ConfigError, Gta6Match, parse_settings
from clipworker.detector.spike import SpikeDetector
from clipworker.ingest import status
from clipworker.live import roster_fields, stream_fields
from clipworker.roster import pick_captures

EXAMPLE = Path(__file__).resolve().parents[1] / "config" / "channels.example.toml"
GTA = {"game_id": "1867279146", "game": "Grand Theft Auto VI"}
OTHER = {"game_id": "509658", "game": "Just Chatting"}


def example(tmp_path):
    return parse_settings(tomllib.loads(EXAMPLE.read_text(encoding="utf-8")), tmp_path)


def test_example_roster_groups_and_archive(tmp_path):
    s = example(tmp_path)
    core = [c.key for c in s.channels if c.group == "core"]
    only = [c.key for c in s.channels if c.group == "gta6_only"]
    assert core == ["twitch:jynxzi", "twitch:lacy", "twitch:xqc", "kick:adinross", "twitch:stableronaldo"]
    assert only == ["twitch:kaicenat", "twitch:ishowspeed"]
    assert all(c.gta6_boost == 1.25 for c in s.channels if c.group == "core")
    assert all(c.gta6_boost == 1.0 for c in s.channels if c.group == "gta6_only")
    # archived streamers keep their crop boxes but are never captured
    arch = {c.login: c for c in s.archived}
    assert set(arch) == {"clix", "silky"} and arch["silky"].layout.facecam_height == 720
    # Lacy keeps his approved box; unapproved proposals are not used yet
    assert [c.login for c in s.channels if c.layout is not None] == ["lacy"]
    assert {c.login: c.name for c in s.channels}["adinross"] == "Adin Ross"
    assert s.max_channels == 3 and s.extra["kick_chatrooms"] == {"875062": "adinross"}


def test_gta6_match_by_id_or_name():
    g = Gta6Match(("1867279146",))
    assert g.matches("1867279146", None)
    assert g.matches(None, "Grand Theft Auto VI (GTA)")      # Kick-style name
    assert g.matches("0", "GTA 6")
    assert not g.matches("3412", "Grand Theft Auto III")
    assert not g.matches("32982", "Grand Theft Auto V")
    assert not g.matches(None, None)


def test_bad_group_and_boost_rejected(tmp_path):
    with pytest.raises(ConfigError):
        parse_settings({"channels": [{"platform": "twitch", "login": "a", "group": "vip"}]}, tmp_path)
    with pytest.raises(ConfigError):
        parse_settings({"channels": [{"platform": "twitch", "login": "a", "gta6_boost": 0.5}]}, tmp_path)


def test_more_channels_than_cap_is_allowed(tmp_path):
    chans = [{"platform": "twitch", "login": f"c{i}"} for i in range(7)]
    assert len(parse_settings({"max_channels": 3, "channels": chans}, tmp_path).channels) == 7


def test_gta6_only_captured_only_on_gta6(tmp_path):
    s = example(tmp_path)
    keys = {c.key for c in s.channels}
    info = {"twitch:kaicenat": {**OTHER, "viewers": 90000}, "twitch:ishowspeed": {**GTA, "viewers": 80000}}
    p = pick_captures(s.channels, info, keys, 3, s.gta6)
    assert p.capture == {"twitch:ishowspeed"}


def test_core_captured_any_game_and_boosted_on_gta6(tmp_path):
    s = example(tmp_path)
    keys = {c.key for c in s.channels}
    info = {"twitch:xqc": {**OTHER, "viewers": 50000}, "twitch:stableronaldo": {**GTA, "viewers": 18000}}
    p = pick_captures(s.channels, info, keys, 3, s.gta6)
    assert p.capture == {"twitch:xqc", "twitch:stableronaldo"}
    assert p.boost["twitch:stableronaldo"] == 1.25 and p.boost["twitch:xqc"] == 1.0
    assert p.boost["twitch:kaicenat"] == 1.0


def test_cap_prefers_gta6_then_core_then_viewers(tmp_path):
    s = example(tmp_path)
    keys = {c.key for c in s.channels}
    info = {"twitch:xqc": {**OTHER, "viewers": 99000},            # core, not GTA
            "kick:adinross": {**GTA, "viewers": 20000},            # core, GTA
            "twitch:stableronaldo": {**GTA, "viewers": 18000},     # core, GTA
            "twitch:kaicenat": {**GTA, "viewers": 90000},          # gta6_only, GTA
            "twitch:ishowspeed": {**GTA, "viewers": 80000}}        # gta6_only, GTA
    p = pick_captures(s.channels, info, keys, 3, s.gta6)
    assert p.capture == {"kick:adinross", "twitch:stableronaldo", "twitch:kaicenat"}
    assert p.skipped == ["twitch:ishowspeed", "twitch:xqc"]


def test_unpermitted_and_archived_never_captured(tmp_path):
    s = example(tmp_path)
    info = {"twitch:clix": GTA, "twitch:xqc": GTA}
    assert pick_captures(s.channels, info, set(), 3, s.gta6).capture == set()
    assert pick_captures(s.channels, info, {"twitch:clix", "twitch:xqc"}, 3, s.gta6).capture == {"twitch:xqc"}


def test_status_parsers_carry_game():
    tw = {"data": [{"user_login": "KaiCenat", "type": "live", "viewer_count": 1, "started_at": "t",
                    "game_id": "1867279146", "game_name": "Grand Theft Auto VI"}]}
    assert status.parse_twitch_streams(tw)["kaicenat"]["game_id"] == "1867279146"
    kk = {"data": [{"slug": "adinross", "category": {"id": 15, "name": "Grand Theft Auto VI (GTA)"},
                    "stream": {"is_live": True, "viewer_count": 5}}]}
    assert status.parse_kick_streams(kk)["adinross"] == {"viewers": 5, "started_at": None,
                                                         "game_id": "15", "game": "Grand Theft Auto VI (GTA)"}


def test_heartbeat_roster_and_games(tmp_path):
    s = example(tmp_path)
    r = roster_fields(s.channels)["roster"]
    assert r["twitch:kaicenat"] == "gta6_only" and r["kick:adinross"] == "core" and "twitch:clix" not in r
    assert stream_fields({"twitch:xqc": {"viewers": 1, "started_at": "t", "game": "GTA VI"}})["games"] == \
        {"twitch:xqc": "GTA VI"}


def test_detector_boost_scales_positive_scores(tmp_path):
    s = example(tmp_path)
    ch = s.channels[0]
    plain, boosted = (SpikeDetector(ch.key, ch.detector, ch.reaction_weights) for _ in range(2))
    boosted.boost = 1.25
    for d in (plain, boosted):
        d.keep_ticks = True
        for t in range(120):
            n = 30 if 100 <= t < 106 else 1
            for i in range(n):
                d.add_message(float(t), f"u{i}", "KEKW")
            d.tick(float(t))
    hi = [(a.score, b.score) for a, b in zip(plain.ticks, boosted.ticks) if a.score > 0.5]
    assert hi and all(b == pytest.approx(a * 1.25) for a, b in hi)


def test_roster_streamers_tracked_without_campaign():
    from clipworker.remote.rights import RightsGate
    camp = {"id": "c1", "status": "active", "streamer_slugs": ["xqc"], "score": 4,
            "rules": {"min_s": 15, "max_s": 45, "required_tags": ["#x"]}}
    gate = RightsGate(lambda: [camp], roster={"lacy", "xqc"})
    own = gate.permit("lacy")
    assert own.campaign_id is None and (own.rules.min_s, own.rules.max_s) == (10, 60)
    assert gate.permit("xqc").campaign_id == "c1"          # a campaign, when active, wins
    assert gate.permit("clix") is None                     # off the roster: still needs a campaign
    assert RightsGate(lambda: []).permit("lacy") is None    # no roster given: old behaviour


def test_streamer_rows_from_roster(tmp_path):
    from clipworker.live import streamer_rows
    rows = {r["slug"]: r for r in streamer_rows(example(tmp_path).channels)}
    assert rows["adinross"] == {"slug": "adinross", "display_name": "Adin Ross", "twitch_login": None,
                                "kick_slug": "adinross"}
    assert rows["jynxzi"]["twitch_login"] == "jynxzi" and "clix" not in rows


def test_heuristic_judge_cuts_around_peak():
    from clipworker.judge.heuristic import HeuristicJudge
    from clipworker.transcribe import Word
    words = [Word(i * 0.5, i * 0.5 + 0.4, f"w{i}") for i in range(120)]
    j = HeuristicJudge().judge(words, [], {"score": 3.0}, "", 60.0, 10, 60, peak_rel=30.0)
    assert j.keep and j.title.startswith("UNJUDGED")
    assert 10 <= j.trim_out - j.trim_in <= 60 and j.trim_in <= 30.0 - 15 and j.trim_out >= 30.0
