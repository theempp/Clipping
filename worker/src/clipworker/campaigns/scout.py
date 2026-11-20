"""campaign-scout, code-first: regex the brief into a record, score it, and
store a DRAFT campaign. Zo activates it in the dashboard; only active
campaigns open the rights gate. Unknown fields stay null ("unverified"),
never guessed. Model help for ambiguous rules text is a later step.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

_MONEY = r"\$\s?(\d{1,3}(?:,\d{3})+|\d+(?:[.,]\d+)?)\s*(k)?"
_CPM = re.compile(_MONEY + r"\s*(?:/|per)\s*(?:1k|1,?000|thousand|k)\b|cpm[^$\n]{0,20}" + _MONEY, re.I)
_CAP = re.compile(r"(?:budget|cap|pool|total)[^$\n]{0,20}" + _MONEY, re.I)
_LEN = re.compile(r"(\d{1,3})\s*(?:-|to|–)\s*(\d{1,3})\s*(?:s|sec|secs|seconds)\b", re.I)
_TAG = re.compile(r"(?<![\w#@])([#@][A-Za-z0-9_]{2,30})")
_DEADLINE = re.compile(r"(?:ends?|deadline|until|through)\s*:?\s*([A-Z][a-z]{2,8}\.? \d{1,2}(?:st|nd|rd|th)?"
                       r"(?:,? \d{4})?|\d{1,2}/\d{1,2}(?:/\d{2,4})?)", re.I)
_X_PLATFORM = re.compile(r"(?:\bon|\band|\bor|,)\s+x\b|\bx\s*/\s*twitter")
PLATFORM_WORDS = {"youtube": ["youtube", "shorts", "yt"], "x": ["twitter", "x.com"],
                  "tiktok": ["tiktok", "tik tok"], "instagram": ["instagram", "reels", "ig", "insta"]}


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


def parse_brief(text: str, roster: list[str]) -> Brief:
    low = f" {text.lower()} "
    streamers = [s for s in roster if re.search(rf"\b{re.escape(s.lower())}\b", low)]
    platforms = [p for p, words in PLATFORM_WORDS.items()
                 if any(re.search(rf"(?<![\w.]){re.escape(w)}(?![\w])", low) for w in words)]
    # bare "X" only in a platform list ("on X", "and X", ", X", "X/Twitter"), not "Lacy x Clix"
    if "x" not in platforms and _X_PLATFORM.search(low):
        platforms.append("x")
    cpm = cap = None
    m = _CPM.search(text)
    if m:
        g = m.groups()
        cpm = _money(g[0], g[1]) if g[0] else _money(g[2], g[3])
    m = _CAP.search(text)
    if m:
        cap = _money(m.group(1), m.group(2))
    lm = _LEN.search(text)
    dl = _DEADLINE.search(text)
    b = Brief(streamers, platforms, cpm, cap, dl.group(1) if dl else None,
              int(lm.group(1)) if lm else None, int(lm.group(2)) if lm else None,
              sorted(set(_TAG.findall(text))))
    b.unverified = [k for k, v in asdict(b).items() if v in (None, []) and k != "unverified"]
    return b


def score(b: Brief, familiar: set[str], our_platforms: set[str] = frozenset({"youtube", "x"})) -> tuple[float, str, str]:
    """0-5 on pay, effort, familiarity, rights clarity, platform fit -> mean, verdict, why."""
    pay = 0 if b.cpm_usd is None else min(5, b.cpm_usd * 2)
    effort = 3 if b.max_s is None else (5 if b.max_s <= 60 else 2)
    fam = 5 if familiar & set(b.streamers) else (2 if b.streamers else 0)
    rights = 5 if b.streamers else 0
    fit = 5 if our_platforms & set(b.platforms) else (1 if b.platforms else 2)
    total = round((pay + effort + fam + rights + fit) / 5, 2)
    if not b.streamers:
        return total, "ask", "no permitted streamer named; rights unclear"
    if b.platforms and not our_platforms & set(b.platforms):
        return total, "avoid", "pays only on platforms we don't auto-post to"
    if b.cpm_usd is None:
        return total, "ask", "pay rate not stated"
    verdict = "pursue" if total >= 3.5 else "ask" if total >= 2.5 else "avoid"
    return total, verdict, f"CPM ${b.cpm_usd:g}, {', '.join(b.streamers)}, score {total}"


def to_campaign_row(b: Brief, title: str, post_id: str | None, total: float, verdict: str, why: str) -> dict:
    rules = {"required_tags": b.tags, "unverified": b.unverified}
    if b.min_s is not None:
        rules["min_s"], rules["max_s"] = b.min_s, b.max_s
    if b.deadline_text:
        rules["deadline_text"] = b.deadline_text
    return {"title": title[:120], "status": "avoid" if verdict == "avoid" else "draft",
            "source": "discord" if post_id else "manual", "source_post_id": post_id,
            "streamer_slugs": b.streamers, "platforms": b.platforms, "cpm_usd": b.cpm_usd,
            "cap_usd": b.cap_usd, "rules": rules, "score": total,
            "recommendation": f"{verdict}: {why}"}
