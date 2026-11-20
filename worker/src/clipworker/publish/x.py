"""X video post: v2 chunked media upload (initialize/append/finalize/status)
then POST /2/tweets. OAuth 2.0 user context (scopes tweet.write, users.read,
media.write, offline.access). Pay-per-use: a post is about $0.015, a post with
a URL about $0.20, so the post text carries no link. Endpoint shapes and
prices must be re-checked on docs.x.com before the first live post.
"""
from __future__ import annotations

import time
from pathlib import Path

import httpx

from .base import PostResult, PublishError

TOKEN_URL = "https://api.x.com/2/oauth2/token"
API = "https://api.x.com/2"
CHUNK = 4 * 1024 * 1024
POST_COST_USD = 0.015


class XPublisher:
    platform = "x"

    def __init__(self, tokens, http: httpx.Client, sleep=time.sleep, max_wait_s: float = 300):
        self.tokens, self.http, self.sleep, self.max_wait_s = tokens, http, sleep, max_wait_s

    def _h(self) -> dict:
        return {"Authorization": f"Bearer {self.tokens.access_token()}"}

    def _ok(self, r: httpx.Response, step: str) -> dict:
        if r.status_code >= 400:
            raise PublishError(f"x {step} {r.status_code}: {r.text[:300]}",
                               retryable=r.status_code >= 500 or r.status_code == 429)
        return r.json() if r.content else {}

    def upload(self, video: Path) -> str:
        size = Path(video).stat().st_size
        j = self._ok(self.http.post(f"{API}/media/upload/initialize", headers=self._h(),
                                    json={"media_type": "video/mp4", "total_bytes": size,
                                          "media_category": "amplify_video"}), "init")
        mid = j["data"]["id"]
        with Path(video).open("rb") as fh:
            for i, chunk in enumerate(iter(lambda: fh.read(CHUNK), b"")):
                self._ok(self.http.post(f"{API}/media/upload/{mid}/append", headers=self._h(),
                                        data={"segment_index": str(i)},
                                        files={"media": ("chunk", chunk, "application/octet-stream")}),
                         "append")
        j = self._ok(self.http.post(f"{API}/media/upload/{mid}/finalize", headers=self._h()), "finalize")
        info = (j.get("data") or {}).get("processing_info")
        waited = 0.0
        while info and info.get("state") in ("pending", "in_progress"):
            if waited > self.max_wait_s:
                raise PublishError("x media processing timed out", retryable=True)
            delay = float(info.get("check_after_secs", 5))
            self.sleep(delay)
            waited += delay
            j = self._ok(self.http.get(f"{API}/media/upload", headers=self._h(),
                                       params={"command": "STATUS", "media_id": mid}), "status")
            info = (j.get("data") or {}).get("processing_info")
        if info and info.get("state") == "failed":
            raise PublishError(f"x media processing failed: {info.get('error')}")
        return mid

    def post(self, video: Path, title: str, description: str, tags: list[str]) -> PostResult:
        mid = self.upload(video)
        text = " ".join([title] + [t if t.startswith("#") else f"#{t}" for t in tags])[:280]
        j = self._ok(self.http.post(f"{API}/tweets", headers=self._h(),
                                    json={"text": text, "media": {"media_ids": [mid]}}), "tweet")
        tid = j["data"]["id"]
        return PostResult(tid, f"https://x.com/i/status/{tid}", j, cost_usd=POST_COST_USD)
