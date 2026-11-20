"""YouTube Shorts upload via Data API v3 videos.insert (resumable).

Quota (2026-11-12 docs): uploads use their own bucket, default 100/day.
Verify current limits and the YouTube API Services Terms before the first
live post (publish-approval-gate step 5).
"""
from __future__ import annotations

from pathlib import Path

import httpx

from .base import PostResult, PublishError

TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"


class YouTubePublisher:
    platform = "youtube"

    def __init__(self, tokens, http: httpx.Client, category_id: str = "20"):  # 20 = Gaming
        self.tokens, self.http, self.category_id = tokens, http, category_id

    def post(self, video: Path, title: str, description: str, tags: list[str]) -> PostResult:
        size = Path(video).stat().st_size
        meta = {"snippet": {"title": title[:100], "description": description[:5000],
                            "tags": tags[:30], "categoryId": self.category_id},
                "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}}
        auth = {"Authorization": f"Bearer {self.tokens.access_token()}"}
        r = self.http.post(UPLOAD_URL, params={"uploadType": "resumable", "part": "snippet,status"},
                           json=meta, headers={**auth, "X-Upload-Content-Type": "video/mp4",
                                               "X-Upload-Content-Length": str(size)})
        if r.status_code >= 400 or "location" not in r.headers:
            raise PublishError(f"youtube init {r.status_code}: {r.text[:300]}",
                               retryable=r.status_code >= 500)
        with Path(video).open("rb") as fh:
            up = self.http.put(r.headers["location"], content=fh.read(),
                               headers={**auth, "Content-Type": "video/mp4"})
        if up.status_code >= 400:
            raise PublishError(f"youtube upload {up.status_code}: {up.text[:300]}",
                               retryable=up.status_code >= 500)
        vid = up.json()["id"]
        return PostResult(vid, f"https://youtube.com/shorts/{vid}", up.json())
