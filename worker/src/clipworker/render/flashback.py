"""Flashback (D113): proposal by code, approval by Zo, intense VHS rewind render. Never automatic.

propose()  finds an earlier moment of the same streamer on the same topic (shared content words) and
           returns a proposal {reason, source_moment, source_file, start, length}; it renders nothing.
render     only runs for a proposal Zo approved: a reversed, VHS-styled segment of that moment with a rewind
           sound is cut into the clip. Viral clips from other places must be downloaded by Zo and named in
           the proposal; this module never fetches anything.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from ..config import Layout
from .ffmpeg import video_filter
from .sfxlib import ensure_sfx
from .tools import enc

STOP = set("""this that with have from they them then than were been will would could should about there their what when
where which while just like going gonna know yeah okay right really very because into over only also your
dont didnt cant wont isnt thats youre theyre here some more most much even still back come came""".split())
MIN_SHARED = 3
SEG_S = 2.8           # seconds of the earlier moment; played back reversed at 2x, so the cut is half that
SPEED = 2.0
LOOKBACK_JOBS = 60


def content_words(words) -> dict[str, float]:
    """{word: first time it is said} for words of 4+ letters that are not filler."""
    out: dict[str, float] = {}
    for w in words:
        t = re.sub(r"[^a-z']", "", str(getattr(w, "text", w.get("text") if isinstance(w, dict) else "")).lower())
        if len(t) >= 4 and t not in STOP:
            out.setdefault(t, float(getattr(w, "start", w.get("start") if isinstance(w, dict) else 0.0)))
    return out


def propose(store, channel: str, words, before_ts: float, exclude_job: str | None = None) -> dict | None:
    """Best earlier moment of this channel on the same topic, or None. Code only, no model."""
    mine = content_words(words)
    if len(mine) < MIN_SHARED:
        return None
    best = None
    for job in store.recent_jobs(channel, before_ts, LOOKBACK_JOBS):
        if job.id == exclude_job:
            continue
        cap = (job.data or {}).get("capture") or {}
        video = cap.get("video")
        if not video or not Path(video).exists() or not job.data.get("words"):
            continue
        theirs = content_words(job.data["words"])
        shared = sorted(set(mine) & set(theirs))
        if len(shared) >= MIN_SHARED and (best is None or len(shared) > len(best[0])):
            best = (shared, job, video, min(theirs[w] for w in shared))
    if best is None:
        return None
    shared, job, video, t0 = best
    title = (job.data.get("judgment") or {}).get("title") or job.id
    return {"reason": f"Same topic as an earlier moment ({', '.join(shared[:5])}): {title}",
            "source_moment": f"{channel} job {job.id} at {t0:.1f}s of its window",
            "source_file": str(video), "start": round(max(0.0, t0 - 0.5), 2), "length": SEG_S,
            "source_job": job.id, "shared": shared[:8]}


def vhs_graph(layout: Layout | None, length: float) -> str:
    """Source window -> 9:16 (same layout as the clip) -> reversed, 2x, VHS noise, colour bleed, scanlines.
    No scale-up of the picture beyond the normal layout crop, so it never reads as a zoom."""
    g = video_filter(layout, None, fps=30)
    return (g[:-3] + "[vv];[vv]reverse,setpts=PTS/" + f"{SPEED:g}"
            + ",noise=alls=38:allf=t+u,rgbashift=rh=-7:bh=7:gv=2,eq=saturation=1.5:contrast=1.18,"
              "drawgrid=w=0:h=6:t=2:c=black@0.28,fps=30,format=yuv420p[v]")


def flashback_segment_command(source: Path, out: Path, start: float, length: float, layout: Layout | None,
                              sfx_wav: Path, ffmpeg: str = "ffmpeg") -> tuple[list[str], float]:
    out_len = length / SPEED
    g = vhs_graph(layout, length) + (f";[1:a]aresample=48000,aformat=channel_layouts=stereo,"
                                     f"apad=whole_dur={out_len:.3f},atrim=0:{out_len:.3f}[a]")
    return [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{start:.3f}", "-t", f"{length:.3f}",
            "-i", str(source), "-i", str(sfx_wav), "-filter_complex", g, "-map", "[v]", "-map", "[a]",
            *enc(out_len), str(out)], out_len


def insert_command(clip: Path, seg: Path, out: Path, dur: float, at: float, fps: int = 30,
                   ffmpeg: str = "ffmpeg") -> list[str]:
    at = min(max(0.3, at), max(0.3, dur - 0.3))
    g = (f"[0:v]trim=0:{at:.3f},setpts=PTS-STARTPTS,fps={fps}[v0];"
         f"[0:a]atrim=0:{at:.3f},asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo[a0];"
         f"[1:v]setpts=PTS-STARTPTS,fps={fps},setsar=1[v1];[1:a]asetpts=PTS-STARTPTS[a1];"
         f"[0:v]trim={at:.3f}:{dur:.3f},setpts=PTS-STARTPTS,fps={fps}[v2];"
         f"[0:a]atrim={at:.3f}:{dur:.3f},asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo[a2];"
         f"[v0][a0][v1][a1][v2][a2]concat=n=3:v=1:a=1[v][a]")
    return [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(clip), "-i", str(seg),
            "-filter_complex", g, "-map", "[v]", "-map", "[a]", "-r", str(fps), *enc(dur + SEG_S / SPEED), str(out)]


def render_flashback(clip: Path, proposal: dict, dur: float, at: float, layout: Layout | None,
                     cache_dir: Path, ffmpeg: str = "ffmpeg", run=subprocess.run) -> float:
    """Cut an APPROVED flashback into `clip` in place; returns the new duration."""
    src = Path(proposal["source_file"])
    if not src.exists():
        raise FileNotFoundError(f"flashback source missing: {src}")
    seg = clip.with_name(clip.stem + ".fb.mp4")
    tmp = clip.with_name(clip.stem + ".fbout.mp4")
    sfx = ensure_sfx("rewind", cache_dir, ffmpeg, run)
    cmd, seg_len = flashback_segment_command(src, seg, float(proposal["start"]),
                                             float(proposal.get("length", SEG_S)), layout, sfx, ffmpeg)
    run(cmd, check=True)
    run(insert_command(clip, seg, tmp, dur, at, ffmpeg=ffmpeg), check=True)
    tmp.replace(clip)
    seg.unlink(missing_ok=True)
    return dur + seg_len
