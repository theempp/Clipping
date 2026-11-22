"""Render a long video with ffmpeg: layout pieces -> body -> freeze-frame cards, voice, ducking, text.

Text design reuses the locked caption style (D048/D050). The headline box treatment follows
Reference Clip Style (white box, dark text) using that style's colours; no new design values.
"""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict
from pathlib import Path

from ..config import CaptionStyle, Layout
from ..render.captions import H, SIDE_MARGIN, W, _esc, ass_time, build_ass, text_width
from ..render.ffmpeg import output_fps, probe, source_fps
from ..transcribe import Word
from .plan import Plan
from .script import Script
from .timeline import Timeline

DUCK = 0.4                     # source under narration: -8 dB
MAX_BYTES = 45 * 1024 * 1024   # headroom under the 50 MB storage limit
HEADLINE_MARGIN_TOP = 260      # below the TikTok top bar
CARD_S = 1.5                   # number card on screen at the start of a topn beat


def _fill(crop) -> str:
    return (f"crop={crop.w}:{crop.h}:{crop.x}:{crop.y},scale={W}:{H}:force_original_aspect_ratio=increase,"
            f"crop={W}:{H},setsar=1")


def piece_filter(mode: str, layout: Layout | None) -> str:
    if mode == "full" or layout is None:
        return f"[0:v]crop=ih*9/16:ih,scale={W}:{H},setsar=1[v]"
    if mode == "game":
        return f"[0:v]{_fill(layout.gameplay)}[v]"
    if mode == "cam":
        return f"[0:v]{_fill(layout.facecam)}[v]"
    fh = layout.facecam_height
    gh = H - fh
    f, p = layout.facecam, layout.gameplay
    return (f"[0:v]split=2[a][b];"
            f"[a]crop={f.w}:{f.h}:{f.x}:{f.y},scale={W}:{fh}:force_original_aspect_ratio=increase,"
            f"crop={W}:{fh},setsar=1[top];"
            f"[b]crop={p.w}:{p.h}:{p.x}:{p.y},scale={W}:{gh}:force_original_aspect_ratio=increase,"
            f"crop={W}:{gh},setsar=1[bot];[top][bot]vstack=inputs=2[v]")


def wrap(text: str, size: int, outline: float, max_px: float) -> str:
    """Greedy word wrap with ASS line breaks so no line overflows the frame."""
    lines, cur = [], ""
    for w in text.split():
        nxt = f"{cur} {w}".strip()
        if cur and text_width(nxt, size, outline) > max_px:
            lines.append(cur)
            cur = w
        else:
            cur = nxt
    if cur:
        lines.append(cur)
    return r"\N".join(_esc(x) for x in lines)


def narration_words(text: str, start: float, end: float) -> list[Word]:
    """Even spread across the line: TTS gives no word timings (good enough for style B)."""
    ws = text.split()
    if not ws:
        return []
    step = (end - start) / len(ws)
    return [Word(start + i * step, start + (i + 1) * step, w) for i, w in enumerate(ws)]


def build_captions(plan: Plan, script: Script, tl: Timeline, style: CaptionStyle) -> str:
    words: list[Word] = []
    if plan.tags.caption_style == "B":
        spans = [(s, e) for k, (s, e) in tl.texts.items() if k.startswith("beat")]
        for i, b in enumerate(plan.beats):   # source words, except under our narration (ducked)
            base = tl.beat_starts[i] - b.t_in
            for w in b.words:
                t = base + w["start"]
                if b.t_in <= w["start"] < b.t_out and not any(s <= t < e for s, e in spans):
                    words.append(Word(t, base + min(w["end"], b.t_out), w["text"]))
        for key, (s, e) in tl.texts.items():
            if key.startswith("beat"):
                words += narration_words(script.beats[int(key[4:]) - 1], s, e)
        words.sort(key=lambda w: w.start)
    doc = build_ass(words, style) if words else build_ass([Word(0, 0.05, " ")], style)
    if not words:   # drop the placeholder event; keep the header and Cap style
        doc = "\n".join(l for l in doc.splitlines() if not l.startswith("Dialogue:")) + "\n"
    head = (f"Style: Head,{style.font},{int(style.size * 0.8)},{style.outline_colour},"
            f"{style.outline_colour},{style.primary_colour},{style.primary_colour},1,0,0,0,100,100,0,0,"
            f"3,18,0,8,{SIDE_MARGIN},{SIDE_MARGIN},{HEADLINE_MARGIN_TOP},1\n"
            f"Style: Card,{style.font},{int(style.size * 1.3)},{style.primary_colour},"
            f"{style.highlight_colour},{style.outline_colour},&H00000000,1,0,0,0,100,100,0,0,"
            f"1,{style.outline},0,5,{SIDE_MARGIN},{SIDE_MARGIN},0,1\n")
    doc = re.sub(r"(^Style: Cap,.*\n)", lambda m: m.group(1) + head, doc, count=1, flags=re.M)
    max_px = W - 2 * SIDE_MARGIN - 40
    ev = [f"Dialogue: 1,{ass_time(0)},{ass_time(tl.total_s)},Head,,0,0,0,,"
          f"{wrap(script.headline.upper(), int(style.size * 0.8), 18, max_px)}"]
    if "hook" in tl.texts:
        s, e = tl.texts["hook"]
        ev.append(f"Dialogue: 2,{ass_time(s)},{ass_time(e)},Card,,0,0,0,,"
                  f"{wrap(script.hook, int(style.size * 1.3), style.outline, max_px)}")
    if "outro" in tl.texts:
        s, e = tl.texts["outro"]
        ev.append(f"Dialogue: 2,{ass_time(s)},{ass_time(e)},Card,,0,0,0,,"
                  f"{wrap(script.outro, int(style.size * 1.3), style.outline, max_px)}")
    for i, card in enumerate(script.cards):
        if card:
            s = tl.beat_starts[i]
            ev.append(f"Dialogue: 2,{ass_time(s)},{ass_time(s + CARD_S)},Card,,0,0,0,,{_esc(card)}")
    return doc + "\n".join(ev) + "\n"


def _bitrate(total_s: float) -> int:
    """kbit/s for video so the file fits the storage limit (audio 160k)."""
    return max(1200, min(6000, int(MAX_BYTES * 8 / total_s / 1000) - 200))


def render_long(plan: Plan, script: Script, tl: Timeline, layout: Layout | None, style: CaptionStyle,
                out_dir: Path, ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe",
                run=subprocess.run) -> dict:
    if style is None:
        raise ValueError("caption_style missing (D022)")
    out_dir.mkdir(parents=True, exist_ok=True)
    fps = output_fps(source_fps(probe(Path(plan.beats[0].video), ffprobe, run)))
    q = ["-r", str(fps), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-crf", "16",
         "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k"]
    parts = []
    for k, p in enumerate(tl.pieces):
        src = Path(plan.beats[p.beat].video).resolve()
        out = out_dir / f"piece{k:02d}.mp4"
        run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{p.t_in:.3f}",
             "-to", f"{p.t_out:.3f}", "-i", str(src), "-filter_complex", piece_filter(p.mode, layout),
             "-map", "[v]", "-map", "0:a:0", *q, str(out)], check=True)
        parts.append(out)
    lst = out_dir / "pieces.txt"
    lst.write_text("".join(f"file '{p.name}'\n" for p in parts), encoding="utf-8")
    body = out_dir / "body.mp4"
    run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
         "-i", lst.name, "-c", "copy", body.name], check=True, cwd=str(out_dir))
    (out_dir / "captions.ass").write_text(build_captions(plan, script, tl, style), encoding="utf-8")
    # final pass: freeze-frame intro/outro, duck source under each line, mix voice, burn text
    ins = ["-i", body.name]
    for wav, _, _ in tl.voice:
        ins += ["-i", str(Path(wav).resolve())]
    duck = "+".join(f"between(t,{s:.3f},{e:.3f})" for _, s, e in tl.voice) or "0"
    intro_ms = int(tl.intro_s * 1000)
    g = [f"[0:v]tpad=start_duration={tl.intro_s:.3f}:start_mode=clone:"
         f"stop_duration={tl.outro_s:.3f}:stop_mode=clone,ass=captions.ass[v]",
         f"[0:a]adelay={intro_ms}|{intro_ms},apad,volume='if({duck},{DUCK},1)':eval=frame[src]"]
    mix = ["[src]"]
    for n, (_, s, _) in enumerate(tl.voice, 1):
        ms = int(s * 1000)
        g.append(f"[{n}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={ms}|{ms}[n{n}]")
        mix.append(f"[n{n}]")
    g.append("".join(mix) + f"amix=inputs={len(mix)}:normalize=0:duration=first,"
             f"loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[a]")
    kbps = _bitrate(tl.total_s)
    final = out_dir / "long.mp4"
    run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", *ins, "-filter_complex", ";".join(g),
         "-map", "[v]", "-map", "[a]", "-t", f"{tl.total_s:.3f}", "-r", str(fps),
         "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p", "-preset", "medium",
         "-crf", "20", "-maxrate", f"{kbps}k", "-bufsize", f"{kbps * 2}k",
         "-c:a", "aac", "-ar", "48000", "-b:a", "160k", "-movflags", "+faststart", final.name],
        check=True, cwd=str(out_dir))
    thumb = out_dir / "thumb.jpg"
    t = tl.beat_starts[0] + plan.beats[0].peak_rel if plan.beats else 1.0
    run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{t:.3f}", "-i", str(final),
         "-frames:v", "1", "-q:v", "3", str(thumb)], check=True)
    for p in parts:
        p.unlink(missing_ok=True)
    manifest = {"plan_id": plan.id, "tags": asdict(plan.tags), "video": str(final),
                "thumbnail": str(thumb), "duration": tl.total_s, "fps": fps,
                "coverage": round(tl.coverage, 3), "max_silent_run_s": round(tl.max_silent_run, 2),
                "pieces": [asdict(p) for p in tl.pieces], "beats": [b.job_id for b in plan.beats],
                "video_kbps": kbps}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
