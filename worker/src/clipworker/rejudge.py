"""Re-judge clips already in review that were cut without a judge (D071 UNJUDGED).

Reads stored judge inputs (words, chat sample, features) from a COPY of the worker store,
calls the judge, and updates only metadata on the pending clip row: title, hook, scores,
judge JSON. Never changes state (only Zo approves/denies, D042) and never re-renders,
so trim points are reported, not applied.
"""
from __future__ import annotations

import shutil
from dataclasses import asdict
from pathlib import Path

from .pipeline import Pipeline
from .remote.rights import RightsGate
from .store import Store
from .transcribe import Word


def rejudge_queue(s, live_db: Path, scratch: Path, sb, judge, apply: bool = True) -> list[dict]:
    scratch.mkdir(parents=True, exist_ok=True)
    db = scratch / "rejudge.sqlite3"
    for suffix in ("", "-wal", "-shm"):  # copy, never write the live store
        src = Path(str(live_db) + suffix)
        if src.exists():
            shutil.copyfile(src, str(db) + suffix)
    store = Store(db)
    pipe = Pipeline(s, store, RightsGate(lambda: [], roster=set()), None, judge, None)
    clips = sb.select("clips", state="eq.pending_review", title="like.UNJUDGED*",
                      select="id,job_id,channel_key,title,judge")
    out = []
    for c in clips:
        try:
            job = store.job(c["job_id"])
        except KeyError:
            job = None
        if job is None or job.channel not in pipe.channels:
            out.append({"clip": c["id"], "skipped": "job not in store"})
            continue
        cap, rules = job.data["capture"], job.data["rules"]
        words = [Word(**w) for w in job.data["words"]]
        feats = {k: v for k, v in job.data["features"].items() if isinstance(v, (int, float))}
        j = judge.judge(words, job.data["chat_sample"], {"score": job.score, **feats},
                        job.data["rules_summary"], cap["end_ts"] - cap["start_ts"],
                        rules["min_s"], rules["max_s"],
                        **({"peak_rel": job.data["peak_ts"] - cap["start_ts"]}
                           if getattr(judge, "wants_peak", False) else {}))
        if j.usage and sb is not None:
            sb.log_spend("grok", judge.cost_usd(j.usage), j.usage.get("total_tokens"),
                         {"job_id": job.id, "rejudge": True})
        if s.features.score_100:
            pipe._score(job, j, words, rules)
        row = {"clip": c["id"], "channel": job.channel, "keep": j.keep, "score": j.score,
               "score_10": j.score_10, "title": j.title, "trim": [j.trim_in, j.trim_out], "reason": j.reason}
        out.append(row)
        if apply:
            prefix = "" if j.keep else "WEAK: "
            sb.update("clips", {"id": c["id"]}, {
                "title": (prefix + j.title)[:200], "hook": j.hook, "category": j.category,
                "confidence": j.confidence, "score_10": j.score_10 or None, "hook_type": j.hook_type,
                "judge": {**asdict(j), "rejudged": True, "unjudged_title": c["title"]}})
    return out
