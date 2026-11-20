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
    assert score(nobody, set())[1] == "ask"


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
