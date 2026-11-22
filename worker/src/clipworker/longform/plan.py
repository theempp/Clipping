"""Long-form planner (D079-D082): group judged moments into one 60 s+ narrated video.

Code only, no model. Input = local worker jobs that passed judging and rendered as short clips.
A plan is a list of beats (one clip each) plus the test tags the video carries.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

from ..store import Job

FORMATS = ("recap", "topn", "explainer", "extended")
PACINGS = ("short", "long")
TARGET_S = {"short": (61.0, 75.0), "long": (120.0, 240.0)}   # runtime window per pacing
CLIPS = {"recap": (2, 5), "topn": (3, 5), "explainer": (2, 6), "extended": (1, 2)}
MIN_SCORE = 6               # judge score_10 floor (same as the short-clip drop rule)
MAX_AGE_S = 72 * 3600       # moments older than this are stale for a recap
LEAD_IN_MAX_S = 8.0         # context pulled in before the judged trim, for narration
INTRO_S = 3.0               # freeze-frame hook card before the first clip
OUTRO_S = 3.0               # freeze-frame end card with the outro question
DONE_STAGES = ("qa_passed", "uploaded")


@dataclass
class Beat:
    job_id: str
    channel: str             # twitch:lacy
    streamer: str            # roster slug
    video: str               # capture file
    t_in: float              # seconds into the capture
    t_out: float
    peak_rel: float          # peak, seconds from t_in
    lead_in_s: float         # context before the judged trim (narration room)
    score_10: int
    title: str
    hook: str
    transcript: str
    chat_sample: list[str] = field(default_factory=list)
    trigger_ts: float = 0.0
    cap_len: float = 0.0     # full capture length (extended format uses all of it)
    words: list[dict] = field(default_factory=list)   # source words, capture-relative (style B)

    @property
    def dur(self) -> float:
        return self.t_out - self.t_in


@dataclass
class Tags:
    channel: str = "zwoclipp"
    format: str = "recap"
    pacing: str = "short"
    caption_style: str = "A"     # D073: A = headline only, B = headline + word captions
    voice: str = "ai"            # ai | zo
    layout: str = "switch"       # switch | stacked


@dataclass
class Plan:
    id: str
    tags: Tags
    beats: list[Beat]
    created_at: str
    state: str = "planned"      # planned -> scripted -> voiced -> rendered -> qa_passed|qa_failed -> uploaded | dropped
    script: dict | None = None
    voice: dict | None = None
    render: dict | None = None
    qa: dict | None = None
    error: str | None = None

    @property
    def clip_s(self) -> float:
        return sum(b.dur for b in self.beats)

    def est_runtime(self) -> float:
        return INTRO_S + self.clip_s + OUTRO_S

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_json(cls, text: str) -> "Plan":
        d = json.loads(text)
        d["tags"] = Tags(**d["tags"])
        d["beats"] = [Beat(**b) for b in d["beats"]]
        return cls(**d)


def beat_from_job(job: Job, streamer: str, lead_in_max: float = LEAD_IN_MAX_S) -> Beat | None:
    """None when the job can't feed a long video (unjudged, weak, sponsored, missing data)."""
    d = job.data
    j = d.get("judgment") or {}
    cap = d.get("capture") or {}
    if not j or not cap.get("video") or not j.get("keep", True):
        return None
    if d.get("campaign_id"):     # D081: campaign/sponsored moments never go on CRP channels
        return None
    if int(j.get("score_10") or 0) < MIN_SCORE:
        return None
    t_in, t_out = float(j["trim_in"]), float(j["trim_out"])
    lead = min(lead_in_max, max(0.0, t_in))     # capture starts before the trim; reuse it as setup
    peak = float(d.get("peak_ts", cap["start_ts"] + t_in)) - cap["start_ts"]
    start = t_in - lead
    return Beat(job_id=job.id, channel=job.channel, streamer=streamer, video=cap["video"],
                t_in=round(start, 3), t_out=round(t_out, 3),
                peak_rel=round(min(max(peak - start, 0.0), t_out - start), 3),
                lead_in_s=round(lead, 3), score_10=int(j.get("score_10") or 0),
                title=j.get("title", ""), hook=j.get("hook", ""),
                transcript=d.get("transcript", ""), chat_sample=list(d.get("chat_sample", []))[-20:],
                trigger_ts=job.trigger_ts,
                words=[w for w in d.get("words", []) if start - 1 <= w["start"] <= t_out + 1],
                cap_len=round(float(cap.get("end_ts", 0)) - float(cap.get("start_ts", 0)), 3))


def widen(b: Beat) -> Beat:
    """Extended format: the whole captured window, judged moment inside it."""
    if b.cap_len <= b.t_out:
        return b
    peak_abs = b.t_in + b.peak_rel
    return Beat(**{**asdict(b), "t_in": 0.0, "t_out": b.cap_len, "peak_rel": round(peak_abs, 3),
                   "lead_in_s": round(b.lead_in_s + b.t_in, 3)})


def _fit(beats: list[Beat], fmt: str, pacing: str) -> list[Beat] | None:
    """Take beats in order until the runtime window is reached; None when too short."""
    lo, hi = TARGET_S[pacing]
    cmin, cmax = CLIPS[fmt]
    out: list[Beat] = []
    for b in beats:
        if len(out) >= cmax:
            break
        if INTRO_S + sum(x.dur for x in out) + b.dur + OUTRO_S > hi and out:
            continue
        out.append(b)
        if len(out) >= cmin and INTRO_S + sum(x.dur for x in out) + OUTRO_S >= lo:
            return out
    if len(out) >= cmin and INTRO_S + sum(x.dur for x in out) + OUTRO_S >= lo:
        return out
    return None


def assemble(candidates: list[Beat], tags: Tags, used: set[str], now: float,
             max_age_s: float = MAX_AGE_S) -> Plan | None:
    """Best plan for these tags, or None if no group reaches the runtime floor."""
    fresh = [b for b in candidates if b.job_id not in used and now - b.trigger_ts <= max_age_s]
    if tags.format == "extended":
        fresh = [widen(b) for b in fresh]
    groups: dict[str, list[Beat]] = {}
    if tags.format == "topn":    # ranked, any roster streamer, best first
        groups["all"] = sorted(fresh, key=lambda b: -b.score_10)
    else:                         # one streamer per video, told in time order
        for b in fresh:
            groups.setdefault(b.streamer, []).append(b)
    best: list[Beat] | None = None
    for key, bs in groups.items():
        # strongest moments first when choosing, then retold chronologically
        picked = _fit(sorted(bs, key=lambda b: -b.score_10), tags.format, tags.pacing)
        if picked and (best is None or sum(b.score_10 for b in picked) > sum(b.score_10 for b in best)):
            best = picked
    if not best:
        return None
    if tags.format != "topn":
        best.sort(key=lambda b: b.trigger_ts)
    else:                          # countdown: #N first, #1 last
        best.sort(key=lambda b: b.score_10)
    return Plan(id=uuid.uuid4().hex[:16], tags=tags, beats=best,
                created_at=datetime.now(timezone.utc).isoformat())


# ---- D082 test schedule -------------------------------------------------------------

@dataclass(frozen=True)
class Schedule:
    start: date
    disabled_formats: tuple[str, ...] = ()
    lead_format: str | None = None      # set after week 2 from results
    lead_pacing: str | None = None

    def tags_for(self, day: date, slot: int, channel: str = "zwoclipp") -> Tags:
        """slot 0/1 = the day's two posts. Weeks 1-2: formats x pacing. Weeks 3-4: one variable."""
        n = (day - self.start).days
        week = n // 7 + 1
        live = [f for f in ("recap", "topn", "explainer", "extended") if f not in self.disabled_formats]
        if not live:
            raise ValueError("every format is disabled; ask zo")
        if week <= 2 or not self.lead_format:
            cells = [(f, p) for f in live for p in PACINGS]
            f, p = cells[(n * 2 + slot) % len(cells)]
            return Tags(channel=channel, format=f, pacing=p)
        f, p = self.lead_format, self.lead_pacing or "short"
        flip = slot == 1                       # slot 0 = control, slot 1 = variant
        if week == 3:
            return Tags(channel=channel, format=f, pacing=p, caption_style="B" if flip else "A")
        if n % 2 == 0:
            return Tags(channel=channel, format=f, pacing=p, voice="zo" if flip else "ai")
        return Tags(channel=channel, format=f, pacing=p, layout="stacked" if flip else "switch")


def load_schedule(path: Path) -> Schedule:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    return Schedule(start=date.fromisoformat(d["start"]),
                    disabled_formats=tuple(d.get("disabled_formats", [])),
                    lead_format=d.get("lead_format"), lead_pacing=d.get("lead_pacing"))


def kill_check(notices: dict[str, int], limit: int = 2) -> list[str]:
    """D082: a format with `limit` or more ineligible/unoriginal notices is disabled."""
    return sorted(f for f, n in notices.items() if n >= limit)
