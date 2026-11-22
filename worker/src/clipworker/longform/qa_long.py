"""clip-qa for long videos: the short-clip checks plus the Creator Rewards rules (D079-D080)."""
from __future__ import annotations

import subprocess
from pathlib import Path

from ..config import Crop, Layout
from ..qa import CampaignRules, QAResult, check_clip
from .script import MIN_COVERAGE

MIN_S = 60.5          # TikTok pays on videos over 1 minute; margin for container rounding
MAX_S = 600.0
MAX_SILENT_S = 25.0   # longest stretch without our narration


def _overlap(a: Crop, b: Crop) -> bool:
    return a.x < b.x + b.w and b.x < a.x + a.w and a.y < b.y + b.h and b.y < a.y + a.h


def check_long(video: Path, captions: Path, manifest: dict, layout: Layout | None,
               logo_boxes: list[Crop] | None = None, title: str = "", description: str = "",
               ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe", run=subprocess.run) -> QAResult:
    rules = CampaignRules(min_s=MIN_S, max_s=MAX_S, permitted=True)
    res = check_clip(video, captions, rules, title, description, ffmpeg, ffprobe, run)
    fails, m = list(res.failures), dict(res.metrics)
    fails = [f.replace(f"outside {MIN_S:.0f}-{MAX_S:.0f}s", f"not over {MIN_S}s") for f in fails]
    cov, silent = manifest.get("coverage", 0.0), manifest.get("max_silent_run_s", 999.0)
    m.update(coverage=cov, max_silent_run_s=silent)
    if cov < MIN_COVERAGE:
        fails.append(f"originality: narration covers {cov:.0%} of runtime (< {MIN_COVERAGE:.0%})")
    if silent > MAX_SILENT_S:
        fails.append(f"originality: {silent:.0f}s stretch with no narration (> {MAX_SILENT_S:.0f}s)")
    if logo_boxes is None:
        m["logo_check"] = "not configured"   # add [channels.logo_boxes] once overlays are mapped
    else:
        crops = [] if layout is None else [layout.facecam, layout.gameplay]
        hit = [b for b in logo_boxes for c in crops if _overlap(b, c)]
        m["logo_check"] = "fail" if hit else "pass"
        if hit:
            fails.append(f"watermark: crop shows {len(hit)} platform logo/overlay box(es)")
    return QAResult(fails, m)
