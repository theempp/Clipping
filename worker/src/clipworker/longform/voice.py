"""Voice track for a long video. `ai` = local Windows TTS (free, offline); `zo` = zo's recordings.

Each narration line becomes its own WAV so the timeline can place it and measure it.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

from .script import Script


class VoiceError(RuntimeError):
    pass


@dataclass
class Line:
    key: str          # hook | beat1.. | outro
    text: str
    wav: str
    dur: float


def line_keys(script: Script) -> list[tuple[str, str]]:
    return ([("hook", script.hook)] + [(f"beat{i + 1}", t) for i, t in enumerate(script.beats)]
            + [("outro", script.outro)])


def wav_duration(path: Path, ffprobe: str = "ffprobe", run=subprocess.run) -> float:
    out = run([ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
              capture_output=True, text=True, check=True).stdout
    return float(json.loads(out)["format"]["duration"])


class Voice(Protocol):
    def speak(self, text: str, out: Path) -> None: ...


class SapiVoice:
    """Windows System.Speech (built into Win 11). Text goes through a file, never the command line."""

    def __init__(self, voice_name: str | None = None, rate: int = 1, run=subprocess.run):
        self.voice_name, self.rate, self.run = voice_name, rate, run

    def speak(self, text: str, out: Path) -> None:
        out.parent.mkdir(parents=True, exist_ok=True)
        txt = out.with_suffix(".txt")
        txt.write_text(text, encoding="utf-8")
        sel = "$s.SelectVoice($env:CLIPP_VOICE);" if self.voice_name else ""
        ps = ("Add-Type -AssemblyName System.Speech;"
              "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;" + sel +
              f"$s.Rate={int(self.rate)};$s.SetOutputToWaveFile($env:CLIPP_OUT);"
              "$s.Speak([IO.File]::ReadAllText($env:CLIPP_TXT));$s.Dispose()")
        import os
        env = {**os.environ, "CLIPP_OUT": str(out), "CLIPP_TXT": str(txt),
               **({"CLIPP_VOICE": self.voice_name} if self.voice_name else {})}
        self.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                 check=True, env=env, capture_output=True)


class RecordedVoice:
    """zo's own reads: one file per line in `dir` (hook.wav, beat1.wav, ..., outro.wav)."""

    def __init__(self, dir: Path):
        self.dir = Path(dir)

    def speak(self, text: str, out: Path) -> None:
        src = next((p for p in (self.dir / f"{out.stem}{ext}" for ext in (".wav", ".m4a", ".mp3", ".webm"))
                    if p.exists()), None)
        if src is None:
            raise VoiceError(f"recording for {out.stem} missing in {self.dir}")
        out.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
                        "-ac", "1", "-ar", "48000", str(out)], check=True)


def voice_lines(script: Script, voice: Voice, out_dir: Path, ffmpeg: str = "ffmpeg",
                ffprobe: str = "ffprobe", run=subprocess.run) -> list[Line]:
    """Speak every line, normalise to -16 LUFS mono 48 kHz, measure it."""
    lines = []
    for key, text in line_keys(script):
        if not text.strip():
            continue
        raw = out_dir / "raw" / f"{key}.wav"
        voice.speak(text, raw)
        wav = out_dir / f"{key}.wav"
        run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(raw),
             "-af", "silenceremove=start_periods=1:start_threshold=-50dB,areverse,"
                    "silenceremove=start_periods=1:start_threshold=-50dB,areverse,"
                    "loudnorm=I=-16:TP=-1.5:LRA=11",
             "-ac", "1", "-ar", "48000", str(wav)], check=True)
        lines.append(Line(key, text, str(wav), round(wav_duration(wav, ffprobe, run), 3)))
    (out_dir / "lines.json").write_text(json.dumps([asdict(x) for x in lines], indent=2), encoding="utf-8")
    return lines
