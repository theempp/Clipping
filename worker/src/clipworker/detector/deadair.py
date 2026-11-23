"""Dead-air gate (D089; zo-clipper reference/live-mode.md). Code only, no model.

- show_start: nothing is clipped before the first `show_start_window_s` window that holds
  `show_start_active_s` seconds of voice activity (starting-soon screens, pre-show music).
- quiet: no voice activity, laugh or shout within peak-20 s .. peak+5 s multiplies the
  moment's score by `quiet_mult` (BRB, ad breaks, menus, map-staring).
- frames (shortlist only): ffmpeg blackdetect + freezedetect on the captured window;
  mostly black or frozen = reject with a logged reason.

Voice activity source today is a loudness proxy (momentary LUFS swing over 3 s: speech
is bursty, music and silence are flat). A real sound-event tagger plugs in through
`add_activity` once its licence is checked (repo-audit). Replay-test before enabling.
"""
from __future__ import annotations

import re
import subprocess
from collections import deque
from pathlib import Path

from ..config import DeadAirParams


class DeadAirGate:
    def __init__(self, p: DeadAirParams):
        self.p = p
        self.show_start: float | None = None
        self._active: deque[float] = deque()      # whole seconds with voice activity
        self._recent: deque[float] = deque()      # same, kept for the quiet check
        self._loud: deque[tuple[float, float]] = deque()

    # feed ----------------------------------------------------------------------------
    def add_activity(self, ts: float, active: bool) -> None:
        if not active:
            return
        sec = float(int(ts))
        if self._recent and self._recent[-1] == sec:
            return
        self._recent.append(sec)
        while self._recent and self._recent[0] < sec - 600:
            self._recent.popleft()
        if self.show_start is None:
            self._active.append(sec)
            while self._active and self._active[0] <= sec - self.p.show_start_window_s:
                self._active.popleft()
            if len(self._active) >= self.p.show_start_active_s:
                self.show_start = self._active[0]

    def add_loudness(self, ts: float, lufs: float) -> None:
        """Loudness proxy for voice activity."""
        self._loud.append((ts, lufs))
        while self._loud and self._loud[0][0] < ts - 3.0:
            self._loud.popleft()
        vals = [v for _, v in self._loud]
        self.add_activity(ts, max(vals) >= self.p.speech_floor_lufs
                          and max(vals) - min(vals) >= self.p.speech_range_lu)

    # checks --------------------------------------------------------------------------
    def started(self, ts: float) -> bool:
        return self.show_start is not None and ts >= self.show_start

    def multiplier(self, peak_ts: float, shout: bool = False) -> float:
        if shout:
            return 1.0
        lo, hi = peak_ts - self.p.quiet_before_s, peak_ts + self.p.quiet_after_s
        return 1.0 if any(lo <= s <= hi for s in self._recent) else self.p.quiet_mult


def words_quiet(words, peak_rel: float, p: DeadAirParams) -> bool:
    """Transcript check on the shortlist: no word within peak-20 s .. peak+5 s."""
    lo, hi = peak_rel - p.quiet_before_s, peak_rel + p.quiet_after_s
    return not any(w.end >= lo and w.start <= hi for w in words)


def dead_air_ratio(words, t_in: float, t_out: float, pad: float = 0.5) -> float:
    """Share of [t_in, t_out] with no speech (words padded by `pad` s each side)."""
    span = t_out - t_in
    if span <= 0:
        return 0.0
    spans = sorted((max(t_in, w.start - pad), min(t_out, w.end + pad))
                   for w in words if w.end + pad > t_in and w.start - pad < t_out)
    covered, cur_s, cur_e = 0.0, None, None
    for s, e in spans:
        if cur_e is None or s > cur_e:
            if cur_e is not None:
                covered += cur_e - cur_s
            cur_s, cur_e = s, e
        else:
            cur_e = max(cur_e, e)
    if cur_e is not None:
        covered += cur_e - cur_s
    return round(max(0.0, 1.0 - covered / span), 3)


_BLACK = re.compile(r"black_duration:\s*([\d.]+)")
_FREEZE = re.compile(r"freeze_duration:\s*([\d.]+)")


def parse_frame_log(stderr: str) -> tuple[float, float]:
    """(black seconds, frozen seconds) from ffmpeg blackdetect/freezedetect output."""
    return (sum(float(x) for x in _BLACK.findall(stderr)),
            sum(float(x) for x in _FREEZE.findall(stderr)))


def frame_reject(video: Path, duration: float, p: DeadAirParams, ffmpeg: str = "ffmpeg",
                 run=subprocess.run) -> str | None:
    """Reason string when the window is mostly black or frozen, else None."""
    if duration <= 0:
        return None
    cmd = [ffmpeg, "-hide_banner", "-nostats", "-i", str(video), "-an",
           "-vf", "fps=4,scale=320:-2,blackdetect=d=0.5:pix_th=0.10,freezedetect=n=0.003:d=2",
           "-f", "null", "-"]
    r = run(cmd, capture_output=True, text=True, timeout=300)
    black, frozen = parse_frame_log(r.stderr or "")
    if black / duration > p.black_max:
        return f"dead air: {black / duration:.0%} black frames"
    if frozen / duration > p.frozen_max:
        return f"dead air: {frozen / duration:.0%} frozen frames (loading/menu/BRB)"
    return None
