"""Live/offline status.

Twitch: Helix GET /streams polled every 60 s with an app access token
(client credentials). Chosen over EventSub because the PC has no public URL
(webhooks) and EventSub-WebSocket needs a user token; polling is 1 call/min,
far inside Helix limits. See Decision Log D040.
Kick: official public API (api.kick.com/public/v1/channels) with an app token
from id.kick.com. Payload field names are UNVERIFIED; parser is tolerant.
"""
from __future__ import annotations

import time

import httpx

TWITCH_TOKEN_URL = "https://id.twitch.tv/oauth2/token"
TWITCH_STREAMS_URL = "https://api.twitch.tv/helix/streams"
KICK_TOKEN_URL = "https://id.kick.com/oauth/token"
KICK_CHANNELS_URL = "https://api.kick.com/public/v1/channels"


class AppToken:
    """Client-credentials token with refresh before expiry."""

    def __init__(self, url: str, client_id: str, client_secret: str, http: httpx.Client):
        self.url, self.client_id, self.client_secret, self.http = url, client_id, client_secret, http
        self._token, self._exp = None, 0.0

    def get(self) -> str:
        if self._token is None or time.time() > self._exp - 300:
            r = self.http.post(self.url, data={"client_id": self.client_id,
                                               "client_secret": self.client_secret,
                                               "grant_type": "client_credentials"})
            r.raise_for_status()
            j = r.json()
            self._token, self._exp = j["access_token"], time.time() + float(j.get("expires_in", 3600))
        return self._token


def parse_twitch_streams(payload: dict) -> dict[str, dict]:
    """login -> {"viewers", "started_at", "game_id", "game"} for live streams only."""
    out = {}
    for d in payload.get("data", []):
        if d.get("type") == "live" and d.get("user_login"):
            out[d["user_login"].lower()] = {"viewers": d.get("viewer_count"), "started_at": d.get("started_at"),
                                            "game_id": d.get("game_id") or None, "game": d.get("game_name") or None,
                                            "user_id": d.get("user_id") or None}
    return out


def twitch_streams(http: httpx.Client, token: AppToken, logins: list[str]) -> dict[str, dict]:
    r = http.get(TWITCH_STREAMS_URL, params=[("user_login", l) for l in logins],
                 headers={"Client-Id": token.client_id, "Authorization": f"Bearer {token.get()}"})
    r.raise_for_status()
    return parse_twitch_streams(r.json())


def twitch_live(http: httpx.Client, token: AppToken, logins: list[str]) -> dict[str, bool]:
    live = twitch_streams(http, token, logins)
    return {l: l in live for l in logins}


def parse_kick_channels(payload: dict) -> dict[str, bool]:
    out = {}
    for d in payload.get("data", []):
        slug = (d.get("slug") or d.get("broadcaster_slug") or "").lower()
        stream = d.get("stream") or {}
        out[slug] = bool(stream.get("is_live", d.get("is_live", False)))
    return out


def parse_kick_streams(payload: dict) -> dict[str, dict]:
    """slug -> {"viewers", "started_at", "game_id", "game"} for live channels.
    `category` {id, name, thumbnail} seen on the real payload 2026-11-21; stream fields still tolerant."""
    out = {}
    for d in payload.get("data", []):
        slug = (d.get("slug") or d.get("broadcaster_slug") or "").lower()
        stream = d.get("stream") or {}
        if slug and stream.get("is_live", d.get("is_live", False)):
            cat = d.get("category") or stream.get("category") or {}
            out[slug] = {"viewers": stream.get("viewer_count", stream.get("viewers")),
                         "started_at": stream.get("start_time") or stream.get("started_at"),
                         "game_id": str(cat["id"]) if cat.get("id") else None,
                         "game": cat.get("name") or None}
    return out


def kick_streams(http: httpx.Client, token: AppToken, slugs: list[str]) -> dict[str, dict]:
    r = http.get(KICK_CHANNELS_URL, params=[("slug", s) for s in slugs],
                 headers={"Authorization": f"Bearer {token.get()}"})
    r.raise_for_status()
    return parse_kick_streams(r.json())


def kick_live(http: httpx.Client, token: AppToken, slugs: list[str]) -> dict[str, bool]:
    live = kick_streams(http, token, slugs)
    return {s: s in live for s in slugs}
