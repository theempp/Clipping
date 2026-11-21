from clipworker.campaigns.discord_bot import handle_post
from clipworker.campaigns.scout import parse_brief, score, to_campaign_row

from fakes import FakeSupabase

BRIEF = """NEW CAMPAIGN: Lacy x Clix highlights
$1.50 per 1k views on YouTube Shorts, TikTok and X. Budget $5,000 total.
Clips must be 15-60 seconds, tag #ReachClipping and @lacy. Ends Dec 15."""


def test_parse_brief_fields():
    b = parse_brief(BRIEF, ["lacy", "clix", "silky"])
    assert b.streamers == ["lacy", "clix"]
    assert set(b.platforms) == {"youtube", "tiktok", "x"}
    assert b.cpm_usd == 1.5 and b.cap_usd == 5000.0
    assert (b.min_s, b.max_s) == (15, 60)
    assert "#ReachClipping" in b.tags and "@lacy" in b.tags
    assert b.deadline_text.startswith("Dec 15")


def test_unknown_fields_stay_unverified():
    b = parse_brief("Silky campaign coming soon", ["silky"])
    assert b.cpm_usd is None and "cpm_usd" in b.unverified
    total, verdict, why = score(b, {"silky"})
    assert verdict == "ask" and "pay" in why


def test_collab_x_is_not_a_platform():
    b = parse_brief("Lacy x Clix collab, $2 per 1k on TikTok", ["lacy", "clix"])
    assert b.platforms == ["tiktok"]


def test_verdicts():
    b = parse_brief(BRIEF, ["lacy", "clix"])
    assert score(b, {"lacy"})[1] == "pursue"
    tiktok_only = parse_brief("Lacy $2 per 1k on TikTok only", ["lacy"])
    assert score(tiktok_only, {"lacy"})[1] == "avoid"
    nobody = parse_brief("$3 per 1k on YouTube", ["lacy"])
    assert score(nobody, set())[1] == "avoid"  # D072: roster only


def test_campaign_row_is_draft_never_active():
    b = parse_brief(BRIEF, ["lacy", "clix"])
    row = to_campaign_row(b, "Lacy x Clix", "post1", *score(b, {"lacy"}))
    assert row["status"] == "draft" and row["rules"]["min_s"] == 15


def test_discord_post_handled_once():
    sb = FakeSupabase()
    a = handle_post(sb, "m1", "c1", "Reach#0001", BRIEF, "2026-11-20T10:00:00+00:00", [],
                    ["lacy", "clix"], {"lacy"})
    b = handle_post(sb, "m1", "c1", "Reach#0001", BRIEF, "2026-11-20T10:00:00+00:00", [],
                    ["lacy", "clix"], {"lacy"})
    assert a["status"] == "draft" and a["recommendation"].startswith("pursue")
    assert b is None and len(sb.t["campaigns"]) == 1


ROSTER = ["jynxzi", "xqc", "adinross", "lacy", "stableronaldo", "kaicenat", "ishowspeed"]
GTA6_ONLY = {"kaicenat", "ishowspeed"}
from clipworker.campaigns.scout import rank_campaigns  # noqa: E402


def test_cpm_floor_is_strictly_above_one_dollar():
    for text, verdict in [("Adin Ross clips $1 per 1k views on YouTube", "avoid"),
                          ("Adin Ross clips $0.80 per 1k on YouTube", "avoid"),
                          ("Adin Ross clips $1.50 per 1k on YouTube Shorts", "pursue")]:
        b = parse_brief(text, ROSTER)
        assert b.streamers == ["adinross"]
        assert score(b, set(ROSTER), gta6_only=GTA6_ONLY)[1] == verdict, text


def test_aliases_find_roster_names():
    b = parse_brief("Stable Ronaldo x Kai Cenat GTA 6 campaign, $2/1k on TikTok and YouTube", ROSTER)
    assert set(b.streamers) == {"stableronaldo", "kaicenat"} and b.gta6


def test_gta6_only_streamer_needs_gta6_campaign():
    b = parse_brief("Kai Cenat highlights, $2 per 1k on YouTube", ROSTER)
    assert score(b, set(ROSTER), gta6_only=GTA6_ONLY)[1] == "ask"
    b = parse_brief("Kai Cenat GTA 6 highlights, $2 per 1k on YouTube", ROSTER)
    assert score(b, set(ROSTER), gta6_only=GTA6_ONLY)[1] == "pursue"


def test_every_rule_line_kept_and_risks_flagged():
    text = """Jynxzi campaign - $2 per 1k views on YouTube
- Clips must be 20-60 seconds
- No reuploads, original edits only
- Minimum 10k views to get paid
- Max $300 per clip
- All clips go through manual review
Do not use AI voices"""
    b = parse_brief(text, ROSTER)
    assert len(b.rules) == 6 and b.min_views == 10000 and b.per_clip_cap_usd == 300
    assert {"original_edit_required", "manual_review", "no_ai_or_bots"} <= set(b.risks)
    row = to_campaign_row(b, "Jynxzi", None, *score(b, set(ROSTER)))
    assert row["rules"]["all_rules"] == b.rules and row["rules"]["min_views"] == 10000
    assert "check rules" in row["recommendation"]


def test_rank_puts_best_paying_pursue_first():
    rows = []
    for t in ["xQc $1.20 per 1k on YouTube", "xQc $3 per 1k on YouTube",
              "Lacy $0.50 per 1k on YouTube", "random streamer $5 per 1k on YouTube"]:
        b = parse_brief(t, ROSTER)
        rows.append(to_campaign_row(b, t, None, *score(b, set(ROSTER))))
    ranked = rank_campaigns(rows)
    assert ranked[0]["title"].startswith("xQc $3") and ranked[0]["rank"] == 1
    assert all(r["recommendation"].startswith("avoid") for r in ranked[-2:])
