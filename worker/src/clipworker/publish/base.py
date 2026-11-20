from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


class PublishError(RuntimeError):
    def __init__(self, msg: str, retryable: bool = False):
        super().__init__(msg)
        self.retryable = retryable


@dataclass
class PostResult:
    external_id: str
    url: str
    raw: dict = field(default_factory=dict)
    cost_usd: float = 0.0


class Publisher(Protocol):
    platform: str

    def post(self, video: Path, title: str, description: str, tags: list[str]) -> PostResult: ...
