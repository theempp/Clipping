"""Grok judgment on the shortlist only (text window, never video).

Input: ~40 s transcript, 30-message chat sample, detector scores, campaign
rules summary. Output: strict JSON (keep/drop, category, trim, hook, title,
emphasis words, confidence). Cached by content hash; spend logged.
Model = cheapest that passes the labeled eval set; set GROK_MODEL in .env.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from ..detector.dedupe import content_hash
from ..transcribe import Word

XAI_URL = "https://api.x.ai/v1/chat/completions"
CATEGORIES = ["funny", "clutch", "rage", "wholesome", "fail", "reaction", "drama", "other"]

SYSTEM = (
    "You judge short-form clip candidates from a live stream. Keep only moments a "
    "stranger would watch to the end: a clear setup and payoff. Respect the campaign "
    "rules. Trim to the tightest window that keeps lead-in and payoff. Times are "
    "seconds from window start. Reply with JSON only, matching the schema."
)

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["keep", "category", "trim_in", "trim_out", "hook", "title",
                 "emphasis_words", "confidence", "reason"],
    "properties": {
        "keep": {"type": "boolean"},
        "category": {"type": "string", "enum": CATEGORIES},
        "trim_in": {"type": "number"},
        "trim_out": {"type": "number"},
        "hook": {"type": "string"},
        "title": {"type": "string"},
        "emphasis_words": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number"},
        "reason": {"type": "string"},
    },
}


class JudgeError(RuntimeError):
    pass


@dataclass
class Judgment:
    keep: bool
    category: str
    trim_in: float
    trim_out: float
    hook: str
    title: str
    emphasis_words: list[str]
    confidence: float
    reason: str
    cached: bool = False
    usage: dict = field(default_factory=dict)


def build_user_prompt(words: list[Word], chat_sample: list[str], scores: dict,
                      rules_summary: str, duration: float) -> str:
    transcript = " ".join(f"[{w.start:.1f}]{w.text}" for w in words)
    chat = "\n".join(chat_sample[:30])
    sc = ", ".join(f"{k}={v:.2f}" if isinstance(v, (int, float)) else f"{k}={v}"
                   for k, v in scores.items())
    return (f"WINDOW_SECONDS: {duration:.1f}\nSCORES: {sc}\nCAMPAIGN_RULES: {rules_summary or 'none'}\n"
            f"TRANSCRIPT:\n{transcript}\nCHAT_SAMPLE:\n{chat}")


def validate(raw: dict, duration: float, min_len: float, max_len: float) -> Judgment:
    missing = [k for k in SCHEMA["required"] if k not in raw]
    if missing:
        raise JudgeError(f"judge output missing {missing}")
    cat = raw["category"] if raw["category"] in CATEGORIES else "other"
    t_in = max(0.0, min(float(raw["trim_in"]), duration))
    t_out = max(t_in, min(float(raw["trim_out"]), duration))
    if t_out - t_in < min_len:  # widen symmetrically inside the window
        pad = (min_len - (t_out - t_in)) / 2
        t_in, t_out = max(0.0, t_in - pad), min(duration, t_out + pad)
    if t_out - t_in > max_len:
        t_out = t_in + max_len
    conf = max(0.0, min(1.0, float(raw["confidence"])))
    return Judgment(bool(raw["keep"]), cat, round(t_in, 2), round(t_out, 2),
                    str(raw["hook"])[:200], str(raw["title"])[:100],
                    [str(w) for w in raw["emphasis_words"]][:12], conf, str(raw["reason"])[:500])


class GrokJudge:
    def __init__(self, api_key: str, model: str, cache_dir: Path, http: httpx.Client | None = None,
                 price_in_per_mtok: float = 0.0, price_out_per_mtok: float = 0.0):
        if not api_key or not model:
            raise JudgeError("XAI_API_KEY and GROK_MODEL must be set")
        self.api_key, self.model = api_key, model
        self.cache = Path(cache_dir) / "judge"
        self.cache.mkdir(parents=True, exist_ok=True)
        self.http = http or httpx.Client(timeout=60)
        self.p_in, self.p_out = price_in_per_mtok, price_out_per_mtok

    def cost_usd(self, usage: dict) -> float:
        return (usage.get("prompt_tokens", 0) * self.p_in
                + usage.get("completion_tokens", 0) * self.p_out) / 1e6

    def judge(self, words: list[Word], chat_sample: list[str], scores: dict, rules_summary: str,
              duration: float, min_len: float = 10.0, max_len: float = 60.0) -> Judgment:
        prompt = build_user_prompt(words, chat_sample, scores, rules_summary, duration)
        key = content_hash(self.model, SYSTEM, prompt)
        f = self.cache / f"{key}.json"
        if f.exists():
            j = validate(json.loads(f.read_text(encoding="utf-8")), duration, min_len, max_len)
            j.cached = True
            return j
        body = {"model": self.model, "temperature": 0,
                "messages": [{"role": "system", "content": SYSTEM},
                             {"role": "user", "content": prompt}],
                "response_format": {"type": "json_schema",
                                    "json_schema": {"name": "clip_judgment", "strict": True,
                                                    "schema": SCHEMA}}}
        r = self.http.post(XAI_URL, json=body, headers={"Authorization": f"Bearer {self.api_key}"})
        if r.status_code >= 400:
            raise JudgeError(f"xAI {r.status_code}: {r.text[:300]}")
        j = r.json()
        try:
            raw = json.loads(j["choices"][0]["message"]["content"])
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            raise JudgeError(f"unparseable judge reply: {e}") from e
        out = validate(raw, duration, min_len, max_len)
        f.write_text(json.dumps(raw), encoding="utf-8")
        out.usage = j.get("usage", {})
        return out
