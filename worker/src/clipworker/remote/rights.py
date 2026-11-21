"""Rights gate. D016 as changed by D070 (Zo, 2026-11-21): roster streamers (the
active channel config) are always captured for Zo's own channels. An ACTIVE
campaign naming the streamer is an extra: it wins and brings its rules. Draft
campaigns (e.g. fresh from Discord) do not count until Zo activates them.
Streamers off the roster still need an active campaign.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from ..qa import CampaignRules


@dataclass
class Permit:
    campaign_id: str | None   # None = own channels (D070), no campaign rules
    title: str
    rules: CampaignRules
    platforms: list[str]
    rules_summary: str


def rules_from(c: dict) -> CampaignRules:
    r = c.get("rules") or {}
    return CampaignRules(min_s=float(r.get("min_s", 10)), max_s=float(r.get("max_s", 60)),
                         required_tags=list(r.get("required_tags", [])),
                         banned_words=list(r.get("banned_words", [])), permitted=True,
                         allow_sfx=bool(r.get("allow_sfx", True)))


def summarize(c: dict) -> str:
    r = c.get("rules") or {}
    parts = [f"length {r.get('min_s', 10)}-{r.get('max_s', 60)}s"]
    if r.get("required_tags"):
        parts.append("must tag " + " ".join(r["required_tags"]))
    if r.get("banned_words"):
        parts.append("avoid " + ", ".join(r["banned_words"]))
    if r.get("notes"):
        parts.append(str(r["notes"])[:300])
    return "; ".join(parts)


class RightsGate:
    def __init__(self, fetch, ttl_s: float = 300, clock=time.time, roster: set[str] | None = None):
        self.fetch, self.ttl, self.clock = fetch, ttl_s, clock
        self.roster = set(roster or ())
        self._cache: list[dict] = []
        self._at = float("-inf")

    def _campaigns(self) -> list[dict]:
        if self.clock() - self._at > self.ttl:
            self._cache, self._at = self.fetch(), self.clock()
        return self._cache

    def permit(self, streamer_slug: str) -> Permit | None:
        """Best active campaign for this streamer (highest score first)."""
        hits = [c for c in self._campaigns()
                if c.get("status") == "active" and streamer_slug in (c.get("streamer_slugs") or [])]
        if not hits:
            if streamer_slug in self.roster:
                return Permit(None, "own channels", rules_from({}), [], "own channels; no campaign rules")
            return None
        c = max(hits, key=lambda c: float(c.get("score") or 0))
        return Permit(c["id"], c.get("title", ""), rules_from(c), list(c.get("platforms") or []),
                      summarize(c))
