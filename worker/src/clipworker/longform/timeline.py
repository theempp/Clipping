"""Timeline of a long video: where each voice line, clip piece and card sits. Pure code."""
from __future__ import annotations

from dataclasses import dataclass, field

from .plan import INTRO_S, OUTRO_S, Plan
from .script import PEAK_GUARD_S
from .voice import Line

LINE_GAP_S = 0.2        # silence before a line starts
TAIL_S = 0.4            # hold after the hook / outro line
PEAK_CAM_S = 0.5        # switch layout: cut to full cam this long before the peak
MIN_PIECE_S = 0.6       # shorter layout pieces merge into their neighbour


class TimelineError(ValueError):
    pass


@dataclass
class Piece:
    beat: int
    mode: str            # stacked | game | cam | full
    t_in: float          # capture seconds
    t_out: float


@dataclass
class Timeline:
    intro_s: float
    outro_s: float
    beat_starts: list[float]                       # absolute start of each beat in the output
    voice: list[tuple[str, float, float]]          # (wav, start, end) absolute
    pieces: list[Piece]
    total_s: float
    texts: dict[str, tuple[float, float]] = field(default_factory=dict)   # line key -> span

    @property
    def coverage(self) -> float:
        return sum(e - s for _, s, e in self.voice) / self.total_s if self.total_s else 0.0

    @property
    def max_silent_run(self) -> float:
        """Longest stretch with no narration (the 'largely repurposed' risk, plan D076)."""
        edges = sorted((s, e) for _, s, e in self.voice)
        t, worst = 0.0, 0.0
        for s, e in edges:
            worst = max(worst, s - t)
            t = max(t, e)
        return max(worst, self.total_s - t)


def _pieces(i: int, t_in: float, t_out: float, narr_end_rel: float, peak_rel: float,
            layout_mode: str, has_layout: bool) -> list[Piece]:
    if not has_layout:
        return [Piece(i, "full", t_in, t_out)]
    if layout_mode == "stacked":
        return [Piece(i, "stacked", t_in, t_out)]
    cuts = [("game", 0.0), ("stacked", max(narr_end_rel, 0.0)),
            ("cam", max(peak_rel - PEAK_CAM_S, 0.0))]
    out: list[Piece] = []
    for k, (mode, start) in enumerate(cuts):
        end = cuts[k + 1][1] if k + 1 < len(cuts) else t_out - t_in
        end = max(start, min(end, t_out - t_in))
        if end - start < MIN_PIECE_S:
            if out:   # too short: the previous piece runs on
                out[-1].t_out = t_in + end
            continue
        if out and out[-1].mode == mode:
            out[-1].t_out = t_in + end
        else:
            out.append(Piece(i, mode, t_in + start, t_in + end))
    if not out:
        out = [Piece(i, "stacked", t_in, t_out)]
    out[-1].t_out = t_out
    return out


def build(plan: Plan, lines: list[Line], has_layout: bool) -> Timeline:
    by = {x.key: x for x in lines}
    hook, outro = by.get("hook"), by.get("outro")
    intro_s = max(INTRO_S, (hook.dur + LINE_GAP_S + TAIL_S) if hook else 0.0)
    outro_s = max(OUTRO_S, (outro.dur + LINE_GAP_S + TAIL_S) if outro else 0.0)
    voice, texts, pieces, starts = [], {}, [], []
    if hook:
        voice.append((hook.wav, LINE_GAP_S, LINE_GAP_S + hook.dur))
        texts["hook"] = (0.0, intro_s)
    t = intro_s
    for i, b in enumerate(plan.beats):
        starts.append(t)
        line = by.get(f"beat{i + 1}")
        narr_end_rel = 0.0
        if line:
            s, e = t + LINE_GAP_S, t + LINE_GAP_S + line.dur
            limit = t + b.peak_rel - PEAK_GUARD_S
            if e > limit + 0.05:
                raise TimelineError(f"beat {i + 1}: narration runs {e - limit:.1f}s into the moment; "
                                    "shorten the line")
            voice.append((line.wav, s, e))
            texts[f"beat{i + 1}"] = (s, e)
            narr_end_rel = e - t
        pieces += _pieces(i, b.t_in, b.t_out, narr_end_rel, b.peak_rel, plan.tags.layout, has_layout)
        t += b.dur
    if outro:
        voice.append((outro.wav, t + LINE_GAP_S, t + LINE_GAP_S + outro.dur))
        texts["outro"] = (t, t + outro_s)
    return Timeline(intro_s=round(intro_s, 3), outro_s=round(outro_s, 3), beat_starts=starts,
                    voice=voice, pieces=pieces, total_s=round(t + outro_s, 3), texts=texts)
