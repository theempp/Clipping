"""Toolbox effects that run on an already rendered 9:16 clip (D114). ffmpeg only, no model.

Each effect is one re-encode pass built from a pure `*_command` function, so it can be unit-tested and
chained. None of them scale or crop the picture, so none can read as a zoom (D112): the vignette is a
darkening of the edges, slow-mo is time only.

  slowmo_vignette  half-speed window with darkened edges, for a punchline
  black_spacer     0.2-0.5 s of black and silence at a time, between jokes in a compilation
  music_cue        a music file under the source audio, ducked while anyone talks
"""
from __future__ import annotations

import subprocess
from pathlib import Path

ENC = ["-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-crf", "20",
       "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-movflags", "+faststart"]


def _atempo(speed: float) -> str:
    """atempo accepts 0.5-2.0 per stage; chain two stages for slower."""
    if speed >= 0.5:
        return f"atempo={speed:.3f}"
    return f"atempo=0.5,atempo={speed / 0.5:.3f}"


def slowmo_vignette_command(src: Path, out: Path, dur: float, at: float, length: float = 1.2,
                            speed: float = 0.5, ffmpeg: str = "ffmpeg") -> tuple[list[str], float]:
    """Slow `length` s of the clip starting at `at` to `speed`, with a vignette on that part only.
    Returns (command, new duration). Needs at least 0.5 s of clip on each side of nothing: `at` is clamped."""
    at = min(max(0.0, at), max(0.0, dur - 0.5))
    end = min(dur, at + length)
    graph = []
    labels = ""
    n = 0
    if at > 0.05:
        graph += [f"[0:v]trim=0:{at:.3f},setpts=PTS-STARTPTS[v{n}]", f"[0:a]atrim=0:{at:.3f},asetpts=PTS-STARTPTS[a{n}]"]
        labels += f"[v{n}][a{n}]"
        n += 1
    graph += [f"[0:v]trim={at:.3f}:{end:.3f},setpts=(PTS-STARTPTS)/{speed:.3f},vignette=PI/4[v{n}]",
              f"[0:a]atrim={at:.3f}:{end:.3f},asetpts=PTS-STARTPTS,{_atempo(speed)}[a{n}]"]
    labels += f"[v{n}][a{n}]"
    n += 1
    if dur - end > 0.05:
        graph += [f"[0:v]trim={end:.3f}:{dur:.3f},setpts=PTS-STARTPTS[v{n}]", f"[0:a]atrim={end:.3f}:{dur:.3f},asetpts=PTS-STARTPTS[a{n}]"]
        labels += f"[v{n}][a{n}]"
        n += 1
    g = ";".join(graph) + f";{labels}concat=n={n}:v=1:a=1[v][a]"
    new_dur = dur + (end - at) * (1 / speed - 1)
    return [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-filter_complex", g,
            "-map", "[v]", "-map", "[a]", *ENC, str(out)], new_dur


def black_spacer_command(src: Path, out: Path, dur: float, at: float, length: float = 0.3,
                         size: tuple[int, int] = (1080, 1920), fps: int = 30,
                         ffmpeg: str = "ffmpeg") -> tuple[list[str], float]:
    """Insert `length` s of black with silence at `at`. Returns (command, new duration)."""
    at = min(max(0.1, at), max(0.1, dur - 0.1))
    w, h = size
    g = (f"[0:v]trim=0:{at:.3f},setpts=PTS-STARTPTS[v0];[0:a]atrim=0:{at:.3f},asetpts=PTS-STARTPTS[a0];"
         f"color=c=black:s={w}x{h}:r={fps}:d={length:.3f},format=yuv420p[v1];"
         f"anullsrc=r=48000:cl=stereo,atrim=0:{length:.3f}[a1];"
         f"[0:v]trim={at:.3f}:{dur:.3f},setpts=PTS-STARTPTS[v2];[0:a]atrim={at:.3f}:{dur:.3f},asetpts=PTS-STARTPTS[a2];"
         f"[v0][a0][v1][a1][v2][a2]concat=n=3:v=1:a=1[v][a]")
    return [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-filter_complex", g,
            "-map", "[v]", "-map", "[a]", "-r", str(fps), *ENC, str(out)], dur + length


def music_cue_command(src: Path, out: Path, music: Path, start: float = 0.0, music_db: float = -16.0,
                      ffmpeg: str = "ffmpeg") -> list[str]:
    """Mix `music` under the clip from `start`, ducking it while the source audio is loud (sidechain),
    then loudnorm the mix to -14 LUFS / -1.5 dBTP like the main render. Source audio stays primary."""
    ms = max(0, int(round(start * 1000)))
    g = (f"[1:a]volume={music_db}dB,adelay={ms}|{ms},aresample=48000[m];"
         f"[0:a]asplit=2[s][sc];"
         f"[m][sc]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[duck];"
         f"[s][duck]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[a]")
    return [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-stream_loop", "-1", "-i", str(music),
            "-filter_complex", g, "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
            "-ar", "48000", "-shortest", "-movflags", "+faststart", str(out)]


def apply_effects(clip: Path, effects: list[dict], dur: float, ffmpeg: str = "ffmpeg",
                  run=subprocess.run) -> float:
    """Run effects in order on `clip` in place. Each effect: {"tool": name, ...params}. Unknown tools and
    tools that need an asset that is missing (music without a file) are skipped, never fatal. Returns the
    new duration. Time-based effects shift later ones, so list them latest first."""
    for e in effects:
        tool = e.get("tool")
        tmp = clip.with_name(clip.stem + ".fx.mp4")
        if tool == "slowmo_vignette":
            cmd, dur = slowmo_vignette_command(clip, tmp, dur, float(e["at"]), float(e.get("length", 1.2)),
                                               float(e.get("speed", 0.5)), ffmpeg)
        elif tool == "black_spacer":
            cmd, dur = black_spacer_command(clip, tmp, dur, float(e["at"]), float(e.get("length", 0.3)),
                                            ffmpeg=ffmpeg)
        elif tool == "music_cue" and e.get("file") and Path(e["file"]).exists():
            cmd = music_cue_command(clip, tmp, Path(e["file"]), float(e.get("start", 0.0)),
                                    float(e.get("db", -16.0)), ffmpeg)
        else:
            continue
        run(cmd, check=True)
        tmp.replace(clip)
    return dur
