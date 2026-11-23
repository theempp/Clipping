"""Chat-spike + loudness detector (Install and Detector Plan, section 2).

Per channel, every 1 s:
  chat  = robust z of 5 s burst rate (max 2 msgs/user) vs rolling 10 min history
  uniq  = robust z of unique chatters in the burst
  react = robust z of mean reaction weight in the burst
  audio = robust z of momentary LUFS vs 10 min history
  score = 0.45 chat + 0.20 uniq + 0.15 react + 0.20 audio   (clamped per term)
Trigger when score >= threshold for >= 2 s. Triggers within 20 s merge into
one moment. 45 s cooldown between moment starts. Window = start-25 s .. start+15 s
(extended to cover a long moment, capped at 90 s). clip-detector-tuning owns
the numbers; they live in DetectorParams per channel.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from ..config import DetectorParams
from .signals import compile_reactions, reaction_weight, robust_z

Z_MIN, Z_MAX = -3.0, 10.0
MAX_WINDOW_S = 90.0
PER_USER_CAP = 2


def _clamp(z: float) -> float:
    return max(Z_MIN, min(Z_MAX, z))


@dataclass
class Moment:
    channel: str
    start_ts: float          # first tick above threshold
    peak_ts: float
    peak_score: float
    last_above_ts: float
    window_start: float = 0.0
    window_end: float = 0.0
    features: dict = field(default_factory=dict)


@dataclass
class Tick:
    ts: float
    score: float
    chat: float
    uniq: float
    react: float
    audio: float
    rate: float


class SpikeDetector:
    def __init__(self, channel: str, params: DetectorParams, reaction_weights: dict[str, float]):
        self.channel = channel
        self.p = params
        self.reactions = compile_reactions(reaction_weights)
        self._msgs: deque[tuple[float, str, float]] = deque()   # ts, user, reaction weight
        self._loud: deque[tuple[float, float]] = deque()
        n = int(params.baseline_s)
        self._h_rate: deque[float] = deque(maxlen=n)
        self._h_uniq: deque[float] = deque(maxlen=n)
        self._h_react: deque[float] = deque(maxlen=n)
        self._h_audio: deque[float] = deque(maxlen=n)
        self._first_tick: float | None = None
        self._above_since: float | None = None
        self._open: Moment | None = None
        self._last_start: float = float("-inf")
        self.ticks: list[Tick] = []  # kept for tuning/replay; trim in live use
        self.keep_ticks = False
        self.boost = 1.0             # GTA 6 boost (D069), set by the live runner per status poll

    def retune(self, params: DetectorParams, reaction_weights: dict[str, float]) -> None:
        """Swap weights live (Streamer Brain) without losing the rolling baseline."""
        if params.baseline_s != self.p.baseline_s:
            raise ValueError("baseline_s cannot change live")
        self.p = params
        self.reactions = compile_reactions(reaction_weights)

    # feed
    def add_message(self, ts: float, user: str, text: str) -> None:
        self._msgs.append((ts, user.lower(), reaction_weight(text, self.reactions)))

    def add_loudness(self, ts: float, lufs: float) -> None:
        if lufs > -70:  # ebur128 reports -inf / -120 on silence; treat as no sample
            self._loud.append((ts, lufs))

    # core
    def _features(self, now: float):
        lo = now - self.p.burst_s
        while self._msgs and self._msgs[0][0] < now - self.p.burst_s - 1:
            self._msgs.popleft()
        burst = [m for m in self._msgs if lo < m[0] <= now]
        per_user: dict[str, int] = {}
        for m in burst:
            per_user[m[1]] = per_user.get(m[1], 0) + 1
        # one chatter counts at most PER_USER_CAP messages per burst: a spammer can't fake a spike
        rate = sum(min(n, PER_USER_CAP) for n in per_user.values()) / self.p.burst_s
        uniq = float(len({m[1] for m in burst}))
        react = (sum(m[2] for m in burst) / len(burst)) if burst else 0.0
        while self._loud and self._loud[0][0] < now - 3:
            self._loud.popleft()
        recent = [v for t, v in self._loud if t <= now]
        audio = recent[-1] if recent else None
        return rate, uniq, react, audio

    def tick(self, now: float) -> Moment | None:
        """Advance to `now` (call once per second). Returns a finished Moment, if any."""
        if self._first_tick is None:
            self._first_tick = now
        rate, uniq, react, audio = self._features(now)
        z_chat = _clamp(robust_z(rate, list(self._h_rate), self.p.rate_floor))
        z_uniq = _clamp(robust_z(uniq, list(self._h_uniq), 1.0))
        z_react = _clamp(robust_z(react, list(self._h_react), 0.15))
        z_audio = 0.0
        if audio is not None:
            z_audio = _clamp(robust_z(audio, list(self._h_audio), 3.0))
            self._h_audio.append(audio)
        self._h_rate.append(rate)
        self._h_uniq.append(uniq)
        self._h_react.append(react)
        score = (self.p.w_chat * z_chat + self.p.w_unique * z_uniq
                 + self.p.w_reaction * z_react + self.p.w_audio * z_audio)
        if score > 0:
            score *= self.boost
        if self.keep_ticks:
            self.ticks.append(Tick(now, score, z_chat, z_uniq, z_react, z_audio, rate))

        warm = now - self._first_tick >= self.p.warmup_s
        above = warm and score >= self.p.threshold
        if above:
            if self._above_since is None:
                self._above_since = now
            sustained = now - self._above_since >= self.p.sustain_s
            if self._open is not None:
                self._open.last_above_ts = now
                if score > self._open.peak_score:
                    self._open.peak_ts, self._open.peak_score = now, score
            elif sustained and self._above_since - self._last_start >= self.p.cooldown_s:
                self._open = Moment(self.channel, self._above_since, now, score, now,
                                    features={"rate": rate, "uniq": uniq, "react": react,
                                              "audio_lufs": audio, "z_chat": z_chat,
                                              "z_uniq": z_uniq, "z_react": z_react,
                                              "z_audio": z_audio, "boost": self.boost})
                self._last_start = self._above_since
        else:
            self._above_since = None
        return self._maybe_close(now)

    def _maybe_close(self, now: float, force: bool = False) -> Moment | None:
        m = self._open
        if m is None or (not force and now - m.last_above_ts < self.p.merge_s):
            return None
        self._open = None
        m.window_start = m.start_ts - self.p.pre_s
        m.window_end = max(m.start_ts + self.p.post_s, m.last_above_ts + 5.0)
        m.window_end = min(m.window_end, m.window_start + MAX_WINDOW_S)
        return m

    def flush(self, now: float) -> Moment | None:
        return self._maybe_close(now, force=True)
