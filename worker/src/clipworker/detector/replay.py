"""Offline replay + eval on stored VOD chat (Build order step 1-2).

Input: TwitchDownloaderCLI `chatdownload` JSON. No video, no model.
Target before going live: recall >= 80% of labeled moments with
<= 10 candidates per hour (Install and Detector Plan, Evaluation).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ..config import DetectorParams
from .spike import Moment, SpikeDetector


def load_twitchdownloader_chat(path: Path) -> list[tuple[float, str, str]]:
    """-> [(offset_seconds, user, text)] sorted by offset."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    out = []
    for c in data.get("comments", []):
        user = (c.get("commenter") or {}).get("name") or "?"
        body = (c.get("message") or {}).get("body") or ""
        out.append((float(c["content_offset_seconds"]), user, body))
    out.sort(key=lambda r: r[0])
    return out


def replay(messages: list[tuple[float, str, str]], params: DetectorParams,
           reactions: dict[str, float], channel: str = "replay",
           loudness: list[tuple[float, float]] | None = None,
           keep_ticks: bool = False, gate=None,
           lift: dict[str, float] | None = None) -> tuple[list[Moment], SpikeDetector]:
    """`gate`: optional DeadAirGate (replay-test it here before enabling live).
    `lift`: a brain's chat-word lift table."""
    det = SpikeDetector(channel, params, reactions, lift=lift)
    det.keep_ticks = keep_ticks
    det.gate = gate
    if not messages:
        return [], det
    loud = sorted(loudness or [])
    t = float(int(messages[0][0]))
    end = messages[-1][0] + params.merge_s + 1
    mi = li = 0
    moments: list[Moment] = []
    while t <= end:
        while mi < len(messages) and messages[mi][0] <= t:
            det.add_message(*messages[mi]); mi += 1
        while li < len(loud) and loud[li][0] <= t:
            det.add_loudness(*loud[li]); li += 1
        m = det.tick(t)
        if m:
            moments.append(m)
        t += 1.0
    m = det.flush(t)
    if m:
        moments.append(m)
    return moments, det


@dataclass
class EvalResult:
    labeled: int
    caught: int
    candidates: int
    hours: float

    @property
    def recall(self) -> float:
        return self.caught / self.labeled if self.labeled else 0.0

    @property
    def per_hour(self) -> float:
        return self.candidates / self.hours if self.hours else 0.0

    @property
    def passes(self) -> bool:
        return self.recall >= 0.8 and self.per_hour <= 10

    def summary(self) -> str:
        return (f"recall {self.caught}/{self.labeled} = {self.recall:.0%}, "
                f"{self.per_hour:.1f} candidates/h over {self.hours:.2f} h -> "
                f"{'PASS' if self.passes else 'FAIL'}")


def evaluate(moments: list[Moment], labels: list[float], duration_s: float) -> EvalResult:
    """A label counts as caught when some candidate window contains it."""
    caught = sum(1 for lab in labels
                 if any(m.window_start <= lab <= m.window_end for m in moments))
    return EvalResult(len(labels), caught, len(moments), duration_s / 3600.0)
