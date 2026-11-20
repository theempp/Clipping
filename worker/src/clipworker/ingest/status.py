"""Live/offline status.

Twitch: Helix GET /streams polled every 60 s with an app access token
(client credentials). Chosen over EventSub because the PC has no public URL
(webhooks) and EventSub-WebSocket needs a user token; polling is 1 call/min,
far inside Helix limits. See Decision Log D032.
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


def twitch_live(http: httpx.Client, token: AppToken, logins: list[str]) -> dict[str, bool]:
    r = http.get(TWITCH_STREAMS_URL, params=[("user_login", l) for l in logins],
                 headers={"Client-Id": token.client_id, "Authorization": f"Bearer {token.get()}"})
    r.raise_for_status()
    live = {d["user_login"].lower() for d in r.json().get("data", []) if d.get("type") == "live"}
    return {l: l in live for l in logins}


def parse_kick_channels(payload: dict) -> dict[str, bool]:
    out = {}
    for d in payload.get("data", []):
        slug = (d.get("slug") or d.get("broadcaster_slug") or "").lower()
        stream = d.get("stream") or {}
        out[slug] = bool(stream.get("is_live", d.get("is_live", False)))
    return out


def kick_live(http: httpx.Client, token: AppToken, slugs: list[str]) -> dict[str, bool]:
    r = http.get(KICK_CHANNELS_URL, params=[("slug", s) for s in slugs],
                 headers={"Authorization": f"Bearer {token.get()}"})
    r.raise_for_status()
    found = parse_kick_channels(r.json())
    return {s: found.get(s, False) for s in slugs}
