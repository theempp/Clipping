"""OAuth2 refresh-token handling for posting accounts.

Initial refresh token comes from .env (<PREFIX>_REFRESH_TOKEN). Rotated tokens
(X rotates on every refresh) are persisted in the local SQLite kv store on the
PC only; never in Supabase, the repo or the vault.
"""
from __future__ import annotations

import time

import httpx

from ..config import env


class TokenSource:
    def __init__(self, token_url: str, prefix: str, kv_get, kv_set, http: httpx.Client,
                 basic_auth: bool = False):
        self.token_url, self.prefix, self.http = token_url, prefix, http
        self.kv_get, self.kv_set, self.basic_auth = kv_get, kv_set, basic_auth
        self.client_id = env(f"{prefix}_CLIENT_ID", required=True)
        self.client_secret = env(f"{prefix}_CLIENT_SECRET") or ""
        self._access, self._exp = None, 0.0

    def _refresh_token(self) -> str:
        tok = self.kv_get(f"oauth:{self.prefix}:refresh") or env(f"{self.prefix}_REFRESH_TOKEN", required=True)
        return tok

    def access_token(self) -> str:
        if self._access and time.time() < self._exp - 120:
            return self._access
        data = {"grant_type": "refresh_token", "refresh_token": self._refresh_token(),
                "client_id": self.client_id}
        auth = None
        if self.basic_auth and self.client_secret:
            auth = (self.client_id, self.client_secret)
        elif self.client_secret:
            data["client_secret"] = self.client_secret
        r = self.http.post(self.token_url, data=data, auth=auth)
        if r.status_code >= 400:
            raise PermissionError(f"{self.prefix} token refresh failed {r.status_code}: {r.text[:200]}")
        j = r.json()
        if j.get("refresh_token"):
            self.kv_set(f"oauth:{self.prefix}:refresh", j["refresh_token"])
        self._access, self._exp = j["access_token"], time.time() + float(j.get("expires_in", 3600))
        return self._access
