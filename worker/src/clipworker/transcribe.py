"""whisperX word timestamps, only on candidate windows, cached by audio hash.

large-v3 float16 on the RTX 5060 (needs CUDA 12.8 torch); CPU fallback medium
int8. English only for V1. Never transcribe whole VODs (token/compute policy).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class Word:
    start: float
    end: float
    text: str


class Transcriber(Protocol):
    def transcribe(self, wav: Path) -> list[Word]: ...


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class CachedTranscriber:
    def __init__(self, inner: Transcriber, cache_dir: Path, version: str = "wx-large-v3-en"):
        self.inner, self.cache_dir, self.version = inner, Path(cache_dir) / "asr", version
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def transcribe(self, wav: Path) -> list[Word]:
        key = f"{self.version}-{file_hash(wav)}"
        f = self.cache_dir / f"{key}.json"
        if f.exists():
            return [Word(**w) for w in json.loads(f.read_text(encoding="utf-8"))]
        words = self.inner.transcribe(wav)
        f.write_text(json.dumps([asdict(w) for w in words]), encoding="utf-8")
        return words


class WhisperXTranscriber:
    def __init__(self, device: str = "cuda", model: str = "large-v3", compute_type: str = "float16",
                 language: str = "en", batch_size: int = 8):
        import whisperx  # optional extra: pip install .[transcribe]
        self._wx = whisperx
        self.device, self.language, self.batch_size = device, language, batch_size
        self.model = whisperx.load_model(model, device, compute_type=compute_type, language=language)
        self.align_model, self.align_meta = whisperx.load_align_model(language_code=language, device=device)

    @classmethod
    def auto(cls) -> "WhisperXTranscriber":
        try:
            import torch
            if torch.cuda.is_available():
                return cls("cuda", "large-v3", "float16")
        except ImportError:
            pass
        return cls("cpu", "medium", "int8")

    def transcribe(self, wav: Path) -> list[Word]:
        audio = self._wx.load_audio(str(wav))
        res = self.model.transcribe(audio, batch_size=self.batch_size, language=self.language)
        res = self._wx.align(res["segments"], self.align_model, self.align_meta, audio, self.device)
        words = []
        for seg in res["segments"]:
            for w in seg.get("words", []):
                if "start" in w and "end" in w:
                    words.append(Word(float(w["start"]), float(w["end"]), w["word"].strip()))
        return words


def words_text(words: list[Word]) -> str:
    return " ".join(w.text for w in words)
