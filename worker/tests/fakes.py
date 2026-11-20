"""In-memory Supabase stand-in: same method surface the worker uses."""
import copy
import itertools
import uuid

from clipworker.states import check_clip


def _match(row, params):
    for k, v in params.items():
        if k in ("select", "order", "limit"):
            continue
        op, _, val = v.partition(".")
        cur = row.get(k)
        if op == "eq" and str(cur).lower() != val.lower():
            return False
        if op == "gte" and (cur is None or str(cur) < val):
            return False
        if op == "is" and val == "null" and cur is not None:
            return False
    return True


class FakeSupabase:
    def __init__(self):
        self.t = {n: [] for n in ("clips", "publications", "destinations", "campaigns", "streamers",
                                  "revisions", "spend", "candidate_log", "worker_heartbeat",
                                  "campaign_posts", "clip_events")}
        self.uploads = {}
        self._seq = itertools.count(1)

    def select(self, table, **params):
        rows = [copy.deepcopy(r) for r in self.t[table] if _match(r, params)]
        if "limit" in params:
            rows = rows[: int(params["limit"])]
        return rows

    def insert(self, table, rows, *, on_conflict=None, ignore_duplicates=False):
        rows = rows if isinstance(rows, list) else [rows]
        out = []
        for r in rows:
            r = {"id": str(uuid.uuid4()), **copy.deepcopy(r)}
            if table == "publications":
                r.setdefault("status", "pending"); r.setdefault("attempts", 0); r.setdefault("response", {})
            if table == "clips":
                r.setdefault("revision", 0)
            if on_conflict:
                keys = on_conflict.split(",")
                hit = next((x for x in self.t[table] if all(x.get(k) == r.get(k) for k in keys)), None)
                if hit is not None:
                    if ignore_duplicates:
                        continue
                    hit.update(r)
                    out.append(copy.deepcopy(hit))
                    continue
            self.t[table].append(r)
            out.append(copy.deepcopy(r))
        return out

    def update(self, table, match, values):
        out = []
        for r in self.t[table]:
            if all(str(r.get(k)) == str(v) for k, v in match.items()):
                r.update(copy.deepcopy(values))
                out.append(copy.deepcopy(r))
        return out

    def upload(self, path, file, content_type):
        self.uploads[path] = open(file, "rb").read()
        return path

    def transition(self, clip, to, reason=None, detail=None):
        row = next(r for r in self.t["clips"] if r["id"] == clip["id"])
        check_clip(row["state"], to, "worker")
        self.t["clip_events"].append({"clip_id": row["id"], "from": row["state"], "to": to,
                                      "actor": "worker", "reason": reason})
        row["state"] = to
        return copy.deepcopy(row)

    def human(self, clip_id, to, reason=None):
        row = next(r for r in self.t["clips"] if r["id"] == clip_id)
        check_clip(row["state"], to, "human")
        row["state"] = to

    def clips_in(self, state, limit=20):
        return self.select("clips", state=f"eq.{state}")

    def heartbeat(self, worker_id, status):
        self.insert("worker_heartbeat", {"worker_id": worker_id, "status": status},
                    on_conflict="worker_id")

    def log_spend(self, kind, usd, units=None, meta=None):
        if usd > 0:
            self.insert("spend", {"kind": kind, "amount_usd": usd})

    def log_candidate(self, row):
        self.insert("candidate_log", row)

    def active_campaigns(self):
        return self.select("campaigns", status="eq.active")

    def destinations(self):
        return [r for r in self.select("destinations") if r.get("active", True)]

    def streamers(self):
        return self.select("streamers")
