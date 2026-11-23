"""Per-streamer brain (D089; zo-clipper reference/streamer-brain.md). Our own build.

One brain per streamer, never shared (no taste transplant): `streamers/<slug>/brain.json`
holds detector weights, a chat-word lift table and counts. Labels come from Zo's review
decisions, viewer clips, CLIP THAT and platform ratios; a weekly refit nudges the weights
(L2 toward the current weights, at most +/-25% per weight per update, last 4 versions kept).
Cold start: the first 3 streams only observe, so the shared defaults stay in charge.
Behind `features.brain`; off = detector uses the fixed weights.
"""
from __future__ import annotations

import datetime as dt
import json
import math
from collections import Counter
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

from .config import DetectorParams
from .detector.signals import message_tokens

FEATURES = ("z_chat", "z_uniq", "z_react", "z_audio", "z_mood", "z_lift")
PARAM = {"z_chat": "w_chat", "z_uniq": "w_unique", "z_react": "w_reaction", "z_audio": "w_audio",
         "z_mood": "w_mood", "z_lift": "w_lift"}
SIGNALS = {"approved": 1.0, "approved_revised": 0.7, "rejected": -1.0, "viewer_clip": 0.6,
           "beat_median": 1.5, "under_median": -0.8, "missed_moment": 1.5, "judge_dropped": -0.2}
COLD_START_STREAMS = 3
MAX_STEP = 0.25        # max relative change per weight per update
MIN_STEP = 0.02        # absolute room for a weight that is still 0
KEEP_VERSIONS = 4
LIFT_MIN, LIFT_MIN_COUNT, LIFT_WINDOW_S = 3.0, 5, 8.0


@dataclass
class Brain:
    streamer: str
    version: int = 0
    weights: dict = field(default_factory=dict)          # feature -> weight; {} = shared defaults
    bias: float | None = None
    baseline: dict = field(default_factory=dict)
    chat_word_lift: dict = field(default_factory=dict)   # TOKEN -> lift
    counts: dict = field(default_factory=lambda: {"streams_watched": 0, "positives": 0, "negatives": 0})
    updated: str | None = None

    @property
    def learning(self) -> bool:
        return self.counts.get("streams_watched", 0) < COLD_START_STREAMS or not self.weights


def load(state_dir: Path, streamer: str) -> Brain:
    f = Path(state_dir) / "brain.json"
    if not f.exists():
        return Brain(streamer)
    d = json.loads(f.read_text(encoding="utf-8"))
    d.pop("streamer", None)
    known = {k: d[k] for k in Brain.__dataclass_fields__ if k in d}
    b = Brain(streamer, **known)
    b.counts = {"streams_watched": 0, "positives": 0, "negatives": 0, **(b.counts or {})}
    return b


def save(b: Brain, state_dir: Path) -> Path:
    """Write brain.json + brain.md; snapshot the version under versions/ (last 4 kept)."""
    d = Path(state_dir)
    (d / "versions").mkdir(parents=True, exist_ok=True)
    body = json.dumps({k: v for k, v in asdict(b).items() if k != "streamer"}, ensure_ascii=False)
    (d / "brain.json").write_text(body + "\n", encoding="utf-8")
    (d / "versions" / f"brain-v{b.version}.json").write_text(body + "\n", encoding="utf-8")
    for old in sorted((d / "versions").glob("brain-v*.json"),
                      key=lambda p: int(p.stem.split("-v")[1]))[:-KEEP_VERSIONS]:
        old.unlink()
    (d / "brain.md").write_text(render_md(b), encoding="utf-8")
    return d / "brain.json"


def apply(b: Brain, params: DetectorParams) -> DetectorParams:
    """Detector params with this streamer's weights; unchanged while learning."""
    if b.learning:
        return params
    return replace(params, **{PARAM[k]: float(v) for k, v in b.weights.items() if k in PARAM})


def current_weights(b: Brain, params: DetectorParams) -> dict:
    return {k: float(b.weights.get(k, getattr(params, PARAM[k]))) for k in FEATURES}


def signal_for_clip(clip: dict) -> str | None:
    """Review decision on a clips row -> label signal."""
    st = clip.get("state")
    if st in ("approved", "scheduled", "published"):
        return "approved_revised" if int(clip.get("revision") or 0) > 0 else "approved"
    if st == "rejected":
        return "rejected"
    return None


def refit(b: Brain, samples: list[tuple[dict, float]], params: DetectorParams,
          l2: float = 1.0, steps: int = 400, lr: float = 0.05) -> dict:
    """Weighted logistic fit of label ~ features, pulled toward the current weights.

    samples: (features, signed label weight). Returns new weights, capped per update and
    rescaled to the current total so the detector threshold keeps its meaning.
    """
    cur = current_weights(b, params)
    data = [([float(f.get(k) or 0.0) for k in FEATURES], 1.0 if w > 0 else 0.0, abs(w))
            for f, w in samples if w]
    if not data or len({y for _, y, _ in data}) < 2:   # need positives and negatives
        return cur
    w = [cur[k] for k in FEATURES]
    bias = 0.0
    total_sw = sum(sw for *_, sw in data)
    for _ in range(steps):
        gw, gb = [0.0] * len(w), 0.0
        for x, y, sw in data:
            z = bias + sum(wi * xi for wi, xi in zip(w, x))
            p = 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))
            for i, xi in enumerate(x):
                gw[i] += sw * (p - y) * xi
            gb += sw * (p - y)
        w = [wi - lr * (g / total_sw + 2 * l2 * (wi - cur[k]) / len(data))
             for wi, g, k in zip(w, gw, FEATURES)]
        bias -= lr * gb / total_sw
    out = {}
    for wi, k in zip(w, FEATURES):
        room = max(MAX_STEP * abs(cur[k]), MIN_STEP)
        out[k] = max(0.0, min(cur[k] + room, max(cur[k] - room, wi)))
    s_cur, s_new = sum(cur.values()), sum(out.values())
    if s_new > 0 and s_cur > 0:
        out = {k: round(v * s_cur / s_new, 4) for k, v in out.items()}
    return out


def chat_word_lift(positive_msgs: list[str], baseline_msgs: list[str],
                   everywhere: set[str] = frozenset()) -> dict:
    """Token frequency in the 8 s after labelled positives / baseline frequency.
    Keep lift >= 3 with >= 5 occurrences; drop emote spam seen in every stream."""
    pos, base = Counter(), Counter()
    for m in positive_msgs:
        pos.update(message_tokens(m))
    for m in baseline_msgs:
        base.update(message_tokens(m))
    n_pos, n_base = max(1, len(positive_msgs)), max(1, len(baseline_msgs))
    out = {}
    for tok, c in pos.items():
        if c < LIFT_MIN_COUNT or tok in everywhere:
            continue
        lift = (c / n_pos) / ((base.get(tok, 0) + 1) / n_base)
        if lift >= LIFT_MIN:
            out[tok] = round(lift, 2)
    return dict(sorted(out.items(), key=lambda kv: -kv[1])[:50])


def update(b: Brain, samples: list[tuple[dict, float]], params: DetectorParams,
           lift: dict | None = None, now: dt.datetime | None = None) -> Brain:
    """New version from labels. Counts always move; weights only after the cold start."""
    pos = sum(1 for _, w in samples if w > 0)
    neg = sum(1 for _, w in samples if w < 0)
    counts = {**b.counts, "positives": b.counts.get("positives", 0) + pos,
              "negatives": b.counts.get("negatives", 0) + neg}
    weights = b.weights
    if b.counts.get("streams_watched", 0) >= COLD_START_STREAMS:
        weights = refit(b, samples, params)
    return replace(b, version=b.version + 1, weights=weights, counts=counts,
                   chat_word_lift=lift if lift is not None else b.chat_word_lift,
                   updated=(now or dt.datetime.now(dt.timezone.utc)).isoformat(timespec="seconds"))


def labels_from_clips(clips: list[dict], streamer: str) -> list[dict]:
    """clip_labels rows for reviewed clips (upsert on streamer, job_id, signal)."""
    rows = []
    for c in clips:
        sig = signal_for_clip(c)
        if sig:
            rows.append({"clip_id": c.get("id"), "job_id": c.get("job_id"), "streamer": streamer,
                         "signal": sig, "weight": SIGNALS[sig], "moment_at": c.get("moment_at"),
                         "reason": (c.get("review_reason") or c.get("reason") or None)})
    return rows


def samples_from_labels(labels: list[dict], store) -> list[tuple[dict, float]]:
    """(detector features, signed weight) for labels whose job is in the local store."""
    out = []
    for lab in labels:
        try:
            job = store.job(lab["job_id"])
        except (KeyError, TypeError):
            continue
        feats = job.data.get("features") or {}
        if feats:
            out.append((feats, float(lab["weight"])))
    return out


def dropped_samples(store, channel: str) -> list[tuple[dict, float]]:
    """Weak negatives: detector fired, the judge dropped it (no Supabase needed)."""
    return [(j.data.get("features") or {}, SIGNALS["judge_dropped"])
            for j in store.jobs_in("dropped")
            if j.channel == channel and "judgment" in j.data and j.data.get("features")]


def learn(b: Brain, sb, store, channel: str, params: DetectorParams, state_dir: Path) -> Brain:
    """Weekly job: review decisions -> clip_labels, labels -> new brain version + snapshot.

    Chat-word lift compares chat around labelled positives with chat around all candidates
    (the store keeps only short chat samples per candidate, not whole streams).
    """
    clips = sb.select("clips", channel_key=f"eq.{channel}",
                      state="in.(approved,scheduled,published,rejected)", select="*")
    rows = labels_from_clips(clips, b.streamer)
    if rows:
        sb.insert("clip_labels", rows, on_conflict="streamer,job_id,signal", ignore_duplicates=True)
    q = {"streamer": f"eq.{b.streamer}", "select": "*"}
    if b.updated:
        q["created_at"] = f"gt.{b.updated}"
    labels = sb.select("clip_labels", **q)
    samples = samples_from_labels(labels, store) + dropped_samples(store, channel)
    pos_jobs = {lab["job_id"] for lab in labels if float(lab["weight"]) > 0}
    pos_msgs, base_msgs = [], []
    for stage in ("dropped", "qa_failed", "uploaded", "qa_passed", "judged", "rendered"):
        for j in store.jobs_in(stage):
            if j.channel == channel:
                sample = j.data.get("chat_sample") or []
                base_msgs += sample
                if j.id in pos_jobs:
                    pos_msgs += sample
    lift = chat_word_lift(pos_msgs, base_msgs) if pos_msgs else None
    nb = update(b, samples, params, lift)
    save(nb, state_dir)
    sb.insert("brain_versions", {"streamer": nb.streamer, "version": nb.version,
                                 "json": {k: v for k, v in asdict(nb).items() if k != "streamer"}},
              on_conflict="streamer,version", ignore_duplicates=True)
    return nb


def note_stream(b: Brain) -> Brain:
    return replace(b, counts={**b.counts, "streams_watched": b.counts.get("streams_watched", 0) + 1})


def render_md(b: Brain) -> str:
    c = b.counts
    lines = [f"# Brain: {b.streamer} (regenerated from brain.json, do not hand-edit)",
             f"Status: {'learning' if b.learning else 'active'} | version: {b.version} | "
             f"streams watched: {c.get('streams_watched', 0)} | positives: {c.get('positives', 0)} | "
             f"negatives: {c.get('negatives', 0)} | updated: {b.updated or '-'}",
             "## Detector weights",
             ("shared defaults (cold start: first 3 streams observe only)" if b.learning else
              " | ".join(f"{k} {v:.3f}" for k, v in b.weights.items())),
             "## What normal looks like",
             (" | ".join(f"{k} {v}" for k, v in b.baseline.items()) or "unknown until 3 streams are watched"),
             "## Words chat spams on big moments",
             (", ".join(f"{t} x{v:g}" for t, v in list(b.chat_word_lift.items())[:15]) or "none yet")]
    return "\n".join(lines) + "\n"
