"""campaign-scout, code-first: regex the brief into a record, score it, and
store a DRAFT campaign. Zo activates it in the dashboard. Unknown fields stay
null ("unverified"), never guessed. Model help for ambiguous rules text is a later step.

Zo's rules (D072, 2026-11-21):
- Only campaigns tied to roster streamers. No roster streamer named = avoid
  (we grow Zo's own channels instead; D070 tracks the roster regardless).
- Hard floor: pay must be MORE than $1 per 1,000 views. $1.00 or less, or a
  pay rate we can't read, never gets "pursue".
- Every rule line in the brief is kept, and risky rules are flagged, so nothing
  is missed before joining. Campaigns are ranked, not just accepted.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

CPM_FLOOR_USD = 1.0     # strictly above this (D072)

_MONEY = r"\$\s?(\d{1,3}(?:,\d{3})+|\d+(?:[.,]\d+)?)\s*(k)?"
_CPM = re.compile(_MONEY + r"\s*(?:/|per)\s*(?:1k|1,?000|thousand|k)\b|cpm[^$\n]{0,20}" + _MONEY, re.I)
_CAP = re.compile(r"(?:budget|cap|pool|total)[^$\n]{0,20}" + _MONEY, re.I)
_PER_CLIP_CAP = re.compile(r"(?:max(?:imum)?|cap(?:ped)?|up to)[^$\n]{0,20}" + _MONEY
                           + r"[^\n]{0,20}(?:per|/|a)\s*(?:clip|video|post|submission)", re.I)
_MIN_VIEWS = re.compile(r"(?:min(?:imum)?|at least)\s*(?:of\s*)?(\d[\d,.]*)\s*(k|m)?\s*views", re.I)
_LEN = re.compile(r"(\d{1,3})\s*(?:-|to|–)\s*(\d{1,3})\s*(?:s|sec|secs|seconds)\b", re.I)
_TAG = re.compile(r"(?<![\w#@])([#@][A-Za-z0-9_]{2,30})")
_DEADLINE = re.compile(r"(?:ends?|deadline|until|through)\s*:?\s*([A-Z][a-z]{2,8}\.? \d{1,2}(?:st|nd|rd|th)?"
                       r"(?:,? \d{4})?|\d{1,2}/\d{1,2}(?:/\d{2,4})?)", re.I)
_X_PLATFORM = re.compile(r"(?:\bon|\band|\bor|,)\s+x\b|\bx\s*/\s*twitter")
_GTA6 = re.compile(r"\b(gta ?(6|vi)|grand theft auto (6|vi))\b", re.I)
_RULE_LINE = re.compile(r"^\s*(?:[-*•>]|\d+[.)]|rule|must|no\b|don'?t|do not|only|required?|"
                        r"never|clips? (?:must|should)|you (?:must|need)|banned|not allowed)", re.I)
PLATFORM_WORDS = {"youtube": ["youtube", "shorts", "yt"], "x": ["twitter", "x.com"],
                  "tiktok": ["tiktok", "tik tok"], "instagram": ["instagram", "reels", "ig", "insta"]}
# Names people use in briefs, per streamers.slug. Unknown slugs fall back to the slug itself.
ALIASES = {"xqc": ["xqc", "xqcow"], "adinross": ["adin ross", "adinross", "adin"],
           "jynxzi": ["jynxzi", "jynxi"], "lacy": ["lacy"],
           "stableronaldo": ["stable ronaldo", "stableronaldo", "stable ron"],
           "kaicenat": ["kai cenat", "kaicenat", "kai"], "ishowspeed": ["ishowspeed", "ishow speed"],
           "clix": ["clix"], "silky": ["silky"]}
# Rules that change whether a campaign is worth it. Flagged, never silently ignored.
RISKS = {
    "manual_review": r"\b(approval|approved by|manual(ly)? review|reviewed before)\b",
    "account_requirements": r"\b(account age|followers? (minimum|required)|verified account|min(imum)? followers)\b",
    "original_edit_required": r"\b(original (content|edit)|no (raw|reupload|re-upload)s?|must be edited|transformative)\b",
    "watermark_or_overlay": r"\b(watermark|overlay|logo|link in bio|cta)\b",
    "no_ai_or_bots": r"\b(no|not|don'?t|never)\b[^.\n]{0,15}\bai\b|\b(ai[- ]generated|bot(ted)? views|view ?bot)\b",
    "exclusive_posting": r"\b(exclusive|only post (here|to)|delete after)\b",
    "views_window": r"\b(views? (counted|within|in the first)|first \d+ (hours|days))\b",
    "payout_threshold": r"\b(min(imum)? payout|payout (min|threshold)|paid (weekly|monthly|after))\b",
}


def _money(num: str, k: str | None) -> float:
    if re.fullmatch(r"\d{1,3}(,\d{3})+", num):
        num = num.replace(",", "")          # 5,000 -> 5000
    v = float(num.replace(",", "."))
    return v * 1000 if k else v


@dataclass
class Brief:
    streamers: list[str]
    platforms: list[str]
    cpm_usd: float | None
    cap_usd: float | None
    deadline_text: str | None
    min_s: int | None
    max_s: int | None
    tags: list[str] = field(default_factory=list)
    unverified: list[str] = field(default_factory=list)
    per_clip_cap_usd: float | None = None
    min_views: int | None = None
    gta6: bool = False                                   # brief mentions GTA 6
    rules: list[str] = field(default_factory=list)       # every rule-like line, verbatim
    risks: list[str] = field(default_factory=list)       # RISKS keys found


def _names(slug: str) -> list[str]:
    return ALIASES.get(slug, [slug])


def parse_brief(text: str, roster: list[str]) -> Brief:
    low = f" {text.lower()} "
    streamers = [s for s in roster
                 if any(re.search(rf"(?<![\w@#]){re.escape(n)}\b", low) for n in _names(s))]
    platforms = [p for p, words in PLATFORM_WORDS.items()
                 if any(re.search(rf"(?<![\w.]){re.escape(w)}(?![\w])", low) for w in words)]
    # bare "X" only in a platform list ("on X", "and X", ", X", "X/Twitter"), not "Lacy x Clix"
    if "x" not in platforms and _X_PLATFORM.search(low):
        platforms.append("x")
    cpm = cap = per_clip = None
    m = _CPM.search(text)
    if m:
        g = m.groups()
        cpm = _money(g[0], g[1]) if g[0] else _money(g[2], g[3])
    m = _CAP.search(text)
    if m:
        cap = _money(m.group(1), m.group(2))
    m = _PER_CLIP_CAP.search(text)
    if m:
        per_clip = _money(m.group(1), m.group(2))
    mv = _MIN_VIEWS.search(text)
    min_views = None
    if mv:
        n = float(mv.group(1).replace(",", ""))
        min_views = int(n * {"k": 1e3, "m": 1e6}.get((mv.group(2) or "").lower(), 1))
    lm = _LEN.search(text)
    dl = _DEADLINE.search(text)
    rules = [ln.strip(" -*•>\t") for ln in text.splitlines() if ln.strip() and _RULE_LINE.search(ln)]
    b = Brief(streamers, platforms, cpm, cap, dl.group(1) if dl else None,
              int(lm.group(1)) if lm else None, int(lm.group(2)) if lm else None,
              sorted(set(_TAG.findall(text))), per_clip_cap_usd=per_clip, min_views=min_views,
              gta6=bool(_GTA6.search(text)), rules=rules,
              risks=[k for k, rx in RISKS.items() if re.search(rx, text, re.I)])
    core = ("streamers", "platforms", "cpm_usd", "cap_usd", "deadline_text", "min_s", "max_s", "tags")
    b.unverified = [k for k in core if getattr(b, k) in (None, [])]
    return b


def score(b: Brief, familiar: set[str], our_platforms: set[str] = frozenset({"youtube", "x"}),
          gta6_only: set[str] = frozenset()) -> tuple[float, str, str]:
    """0-5 on pay, effort, familiarity, rights clarity, platform fit, rule risk -> mean, verdict, why."""
    pay = 0 if b.cpm_usd is None else max(0.0, min(5.0, (b.cpm_usd - CPM_FLOOR_USD) * 2.5))
    if b.per_clip_cap_usd is not None and b.per_clip_cap_usd < 20:
        pay = min(pay, 2)                                  # small per-clip cap limits upside
    if b.cap_usd is not None and b.cap_usd < 500:
        pay = min(pay, 2)                                  # tiny pool fills fast
    effort = 3 if b.max_s is None else (5 if b.max_s <= 60 else 2)
    fam = 5 if familiar & set(b.streamers) else (2 if b.streamers else 0)
    rights = 5 if b.streamers else 0
    fit = 5 if our_platforms & set(b.platforms) else (1 if b.platforms else 2)
    risk = max(0, 5 - len(b.risks))
    total = round((pay + effort + fam + rights + fit + risk) / 6, 2)
    if not b.streamers:
        return total, "avoid", "not tied to a roster streamer; grow own channels instead"
    if b.platforms and not our_platforms & set(b.platforms):
        return total, "avoid", "pays only on platforms we don't auto-post to"
    if b.cpm_usd is None:
        return total, "ask", "pay rate not stated; must be above $1 per 1K views to join"
    if b.cpm_usd <= CPM_FLOOR_USD:
        return total, "avoid", f"pays ${b.cpm_usd:g} per 1K views; rule is more than $1"
    if set(b.streamers) <= gta6_only and not b.gta6:
        return total, "ask", "Kai/Speed are clipped on GTA 6 only; check GTA 6 clips qualify"
    verdict = "pursue" if total >= 3.5 else "ask" if total >= 2.5 else "avoid"
    flags = f"; check rules: {', '.join(b.risks)}" if b.risks else ""
    return total, verdict, f"CPM ${b.cpm_usd:g}, {', '.join(b.streamers)}, score {total}{flags}"


_ORDER = {"pursue": 0, "ask": 1, "avoid": 2}


def rank_campaigns(rows: list[dict]) -> list[dict]:
    """Best first: verdict, then score, then CPM. Adds `rank` (1-based)."""
    def key(r):
        verdict = (r.get("recommendation") or "avoid").split(":", 1)[0]
        return (_ORDER.get(verdict, 3), -float(r.get("score") or 0), -float(r.get("cpm_usd") or 0))
    out = sorted(rows, key=key)
    for i, r in enumerate(out, 1):
        r["rank"] = i
    return out


def to_campaign_row(b: Brief, title: str, post_id: str | None, total: float, verdict: str, why: str) -> dict:
    rules = {"required_tags": b.tags, "unverified": b.unverified, "all_rules": b.rules,
             "risks": b.risks, "gta6": b.gta6}
    if b.min_s is not None:
        rules["min_s"], rules["max_s"] = b.min_s, b.max_s
    if b.deadline_text:
        rules["deadline_text"] = b.deadline_text
    if b.per_clip_cap_usd is not None:
        rules["per_clip_cap_usd"] = b.per_clip_cap_usd
    if b.min_views is not None:
        rules["min_views"] = b.min_views
    return {"title": title[:120], "status": "avoid" if verdict == "avoid" else "draft",
            "source": "discord" if post_id else "manual", "source_post_id": post_id,
            "streamer_slugs": b.streamers, "platforms": b.platforms, "cpm_usd": b.cpm_usd,
            "cap_usd": b.cap_usd, "rules": rules, "score": total,
            "recommendation": f"{verdict}: {why}"}


KEEP_STATUSES = {"joined", "declined", "left"}   # Zo's call on a pod_campaigns row; never overwritten


def score_for_pod(campaign: dict, pod_slugs: set[str]) -> dict:
    """Active campaign vs one pod's streamers -> scout json (verdict, why, overlap). D072 floor."""
    overlap = sorted(set(campaign.get("streamer_slugs") or []) & pod_slugs)
    cpm, total = campaign.get("cpm_usd"), float(campaign.get("score") or 0)
    if not overlap:
        verdict, why = "avoid", "no streamer in this pod"
    elif cpm is None:
        verdict, why = "ask", "pay rate not stated; must be above $1 per 1K views to join"
    elif float(cpm) <= CPM_FLOOR_USD:
        verdict, why = "avoid", f"pays ${float(cpm):g} per 1K views; rule is more than $1"
    else:
        verdict = "pursue" if total >= 3.5 else "ask" if total >= 2.5 else "avoid"
        why = f"CPM ${float(cpm):g}, {', '.join(overlap)}, score {total}"
    return {"verdict": verdict, "why": why, "streamers": overlap, "cpm_usd": cpm, "score": total}


def scout_pods(sb) -> int:
    """[scout] per_pod: upsert pod_campaigns 'suggested' rows for each pod's worthwhile active
    campaigns. Rows Zo already joined/declined/left are left alone. Returns rows written."""
    streamers = sb.select("streamers", select="slug,pod_id")
    campaigns = sb.active_campaigns()
    n = 0
    for pod in sb.select("pods", status="neq.ended", select="id,slug"):
        slugs = {s["slug"] for s in streamers if s.get("pod_id") == pod["id"]}
        have = {r["campaign_id"]: r["status"] for r in
                sb.select("pod_campaigns", pod_id=f"eq.{pod['id']}", select="campaign_id,status")}
        rows = []
        for c in campaigns:
            if have.get(c["id"]) in KEEP_STATUSES:
                continue
            sc = score_for_pod(c, slugs)
            if sc["verdict"] != "avoid":
                rows.append({"pod_id": pod["id"], "campaign_id": c["id"], "status": "suggested", "scout": sc})
        if rows:
            sb.insert("pod_campaigns", rows, on_conflict="pod_id,campaign_id")
            n += len(rows)
    return n
