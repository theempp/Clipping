"""Thin Supabase client (PostgREST + Storage) for the worker. Service role key
lives only in C:\\clip-work\\worker\\.env. The worker can only move clips along
the WORKER_MOVES edges; the database enforces the same rule.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from ..states import check_clip


def _now_iso() -> str:
    import datetime as dt
    return dt.datetime.now(dt.timezone.utc).isoformat()


class SupabaseError(RuntimeError):
    pass


class Supabase:
    def __init__(self, url: str, service_key: str, http: httpx.Client | None = None,
                 bucket: str = "clips"):
        if not url or not service_key:
            raise SupabaseError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
        self.url = url.rstrip("/")
        self.bucket = bucket
        self.http = http or httpx.Client(timeout=120)
        self.h = {"apikey": service_key, "Authorization": f"Bearer {service_key}"}

    def _check(self, r: httpx.Response) -> Any:
        if r.status_code >= 400:
            raise SupabaseError(f"{r.request.method} {r.request.url.path} -> {r.status_code}: {r.text[:300]}")
        return r.json() if r.content else None

    # generic
    def select(self, table: str, **params) -> list[dict]:
        return self._check(self.http.get(f"{self.url}/rest/v1/{table}", params=params, headers=self.h))

    def insert(self, table: str, rows: dict | list[dict], *, on_conflict: str | None = None,
               ignore_duplicates: bool = False) -> list[dict]:
        prefer = ["return=representation"]
        params = {}
        if on_conflict:
            params["on_conflict"] = on_conflict
            prefer.append("resolution=" + ("ignore-duplicates" if ignore_duplicates else "merge-duplicates"))
        return self._check(self.http.post(f"{self.url}/rest/v1/{table}", params=params, json=rows,
                                          headers={**self.h, "Prefer": ",".join(prefer)}))

    def update(self, table: str, match: dict[str, str], values: dict) -> list[dict]:
        params = {k: f"eq.{v}" for k, v in match.items()}
        return self._check(self.http.patch(f"{self.url}/rest/v1/{table}", params=params, json=values,
                                           headers={**self.h, "Prefer": "return=representation"}))

    def rpc(self, fn: str, args: dict) -> Any:
        return self._check(self.http.post(f"{self.url}/rest/v1/rpc/{fn}", json=args, headers=self.h))

    # storage
    def upload(self, path: str, file: Path, content_type: str) -> str:
        with Path(file).open("rb") as fh:
            r = self.http.post(f"{self.url}/storage/v1/object/{self.bucket}/{path}", content=fh.read(),
                               headers={**self.h, "Content-Type": content_type, "x-upsert": "true"})
        self._check(r)
        return path

    # domain helpers
    def transition(self, clip: dict, to: str, reason: str | None = None, detail: dict | None = None) -> dict:
        check_clip(clip["state"], to, "worker")
        return self.rpc("worker_transition", {"p_clip": clip["id"], "p_to": to, "p_reason": reason,
                                              "p_detail": detail or {}})

    def clips_in(self, state: str, limit: int = 20) -> list[dict]:
        return self.select("clips", state=f"eq.{state}", order="created_at.asc", limit=str(limit))

    def heartbeat(self, worker_id: str, status: dict) -> None:
        self.insert("worker_heartbeat", {"worker_id": worker_id, "seen_at": _now_iso(), "status": status},
                    on_conflict="worker_id")

    def log_spend(self, kind: str, usd: float, units: float | None = None, meta: dict | None = None) -> None:
        if usd > 0:
            self.insert("spend", {"kind": kind, "amount_usd": round(usd, 5), "units": units,
                                  "meta": meta or {}})

    def log_candidate(self, row: dict) -> None:
        self.insert("candidate_log", row)

    def active_campaigns(self) -> list[dict]:
        return self.select("campaigns", status="eq.active", select="*")

    def destinations(self) -> list[dict]:
        return self.select("destinations", active="eq.true", select="*")

    def streamers(self) -> list[dict]:
        return self.select("streamers", select="*")
