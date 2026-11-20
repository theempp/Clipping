"""One clock for chat, loudness and video segments (stream-ingest rule 1).

All pipeline timestamps are float seconds on the worker's wall clock, captured
via a monotonic source anchored once at start, so NTP jumps never reorder
events. Drift between anchored time and the system wall clock is logged.
"""
from __future__ import annotations

import logging
import time

log = logging.getLogger(__name__)


class Clock:
    def __init__(self, wall=time.time, mono=time.monotonic, drift_warn_s: float = 0.5):
        self._wall, self._mono = wall, mono
        self._anchor_wall = wall()
        self._anchor_mono = mono()
        self.drift_warn_s = drift_warn_s

    def now(self) -> float:
        return self._anchor_wall + (self._mono() - self._anchor_mono)

    def drift(self) -> float:
        return self._wall() - self.now()

    def check_drift(self) -> float:
        d = self.drift()
        if abs(d) > self.drift_warn_s:
            log.warning("clock drift %.3fs vs system wall clock", d)
        return d
