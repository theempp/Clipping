"""Narration script: the one model step of a long video (D080: our words carry every video).

The model sees text only: transcript windows, judge fields, a few chat lines. Code checks the
reply (word budgets, no copied transcript, no invented numbers) before anything is voiced.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import httpx

from ..detector.dedupe import content_hash
from ..judge.grok import XAI_URL
from .plan import INTRO_S, OUTRO_S, Plan

WPS = 2.5                 # 150 words a minute
PEAK_GUARD_S = 0.4        # narration ends this long before a beat's peak (the reaction plays clean)
COPY_NGRAM = 6            # a 6-word run shared with the transcript = copied, not ours
MIN_COVERAGE = 0.40       # narration share of runtime (originality floor, plan D080)

SYSTEM = (
    "You write voiceover for a TikTok channel that retells livestream moments. Your narration is "
    "the original part of the video: context the clip does not show, who is involved, why it "
    "matters, what happened next. Rules: stay inside each word budget; never repeat what the "
    "streamer says in the transcript; use only facts present in the inputs (no invented numbers, "
    "names or events); plain spoken English, present tense, no hashtags or emojis in narration; "
    "headline = 2-6 words for the static on-screen title. Reply with JSON only."
)

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["headline", "hook", "beats", "outro", "title", "caption", "hashtags"],
    "properties": {
        "headline": {"type": "string"},
        "hook": {"type": "string"},
        "beats": {"type": "array", "items": {"type": "string"}},
        "outro": {"type": "string"},
        "title": {"type": "string"},
        "caption": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
    },
}


class ScriptError(RuntimeError):
    pass


@dataclass
class Script:
    headline: str
    hook: str
    beats: list[str]
    outro: str
    title: str
    caption: str
    hashtags: list[str]
    cards: list[str]           # number cards for topn ("#3"), empty strings otherwise
    usage: dict | None = None
    cached: bool = False


def budgets(plan: Plan) -> tuple[int, list[int], int]:
    """(hook, per-beat, outro) word budgets from the time available before each peak."""
    beat = [max(0, int((b.peak_rel - PEAK_GUARD_S) * WPS)) for b in plan.beats]
    return int(INTRO_S * WPS), beat, int(OUTRO_S * WPS)


def runtime(plan: Plan) -> float:
    return INTRO_S + plan.clip_s + OUTRO_S


def feasible(plan: Plan) -> tuple[bool, str]:
    """Before any model spend: can narration reach the coverage floor at all?"""
    h, bs, o = budgets(plan)
    room = (h + sum(bs) + o) / WPS
    need = MIN_COVERAGE * runtime(plan)
    if room < need:
        return False, f"narration room {room:.1f}s < {need:.1f}s needed (40% of {runtime(plan):.1f}s)"
    return True, ""


def build_prompt(plan: Plan) -> str:
    h, bs, o = budgets(plan)
    lines = [f"Format: {plan.tags.format}. Pacing: {plan.tags.pacing}. Channel: streamer story recaps.",
             f"hook: max {h} words (said over the opening title card).",
             f"outro: max {o} words, one question that invites comments."]
    if plan.tags.format == "topn":
        lines.append(f"Countdown from #{len(plan.beats)} to #1; beats are in that order.")
    for i, b in enumerate(plan.beats, 1):
        lines += [f"--- beat {i}: streamer {b.streamer}, max {bs[i - 1]} words "
                  f"(said over the {b.lead_in_s:.0f}s lead-up, before the moment hits)",
                  f"judge title: {b.title}", f"judge hook: {b.hook}",
                  f"transcript: {b.transcript[:700]}",
                  "chat: " + " | ".join(c[:60] for c in b.chat_sample[-10:])]
    return "\n".join(lines)


_WORD = re.compile(r"[A-Za-z0-9']+")
_NUM = re.compile(r"\d+(?:[.,]\d+)?")


def _words(s: str) -> list[str]:
    return [w.lower() for w in _WORD.findall(s)]


def _ngrams(ws: list[str], n: int) -> set[tuple[str, ...]]:
    return {tuple(ws[i:i + n]) for i in range(len(ws) - n + 1)}


def validate(raw: dict, plan: Plan) -> Script:
    h, bs, o = budgets(plan)
    beats = [str(x).strip() for x in raw.get("beats", [])]
    if len(beats) != len(plan.beats):
        raise ScriptError(f"{len(beats)} beat lines for {len(plan.beats)} beats")
    parts = [("hook", str(raw.get("hook", "")).strip(), h), ("outro", str(raw.get("outro", "")).strip(), o)]
    parts += [(f"beat {i + 1}", t, bs[i]) for i, t in enumerate(beats)]
    for name, text, cap in parts:
        n = len(_words(text))
        if cap and n == 0 and name in ("hook", "outro"):
            raise ScriptError(f"{name} is empty")
        if n > cap + 1:
            raise ScriptError(f"{name}: {n} words over budget {cap}")
    source = " ".join(f"{b.transcript} {b.title} {b.hook} {' '.join(b.chat_sample)} {b.streamer}"
                      for b in plan.beats)
    src_grams = _ngrams(_words(source), COPY_NGRAM)
    src_nums = set(_NUM.findall(source)) | {str(i) for i in range(1, len(plan.beats) + 1)}
    for name, text, _ in parts:
        if _ngrams(_words(text), COPY_NGRAM) & src_grams:
            raise ScriptError(f"{name} copies the transcript")
        bad = [x for x in _NUM.findall(text) if x not in src_nums]
        if bad:
            raise ScriptError(f"{name} has numbers not in the inputs: {bad}")
    headline = str(raw.get("headline", "")).strip()
    if not 1 <= len(_words(headline)) <= 6:
        raise ScriptError("headline must be 1-6 words")
    title = str(raw.get("title", "")).strip()[:90]
    if not title:
        raise ScriptError("title is empty")
    tags = [("#" + t.lstrip("#")).replace(" ", "") for t in raw.get("hashtags", []) if str(t).strip()][:5]
    n = len(plan.beats)
    cards = [f"#{n - i}" for i in range(n)] if plan.tags.format == "topn" else [""] * n
    return Script(headline=headline, hook=parts[0][1], beats=beats, outro=parts[1][1], title=title,
                  caption=str(raw.get("caption", "")).strip()[:300], hashtags=tags, cards=cards)


class Writer(Protocol):
    def write(self, plan: Plan) -> Script: ...


class GrokWriter:
    """One text call per plan, cached by content hash; one retry on a failed check."""

    def __init__(self, api_key: str, model: str, cache_dir: Path, http: httpx.Client | None = None,
                 price_in_per_mtok: float = 0.0, price_out_per_mtok: float = 0.0):
        if not api_key or not model:
            raise ScriptError("XAI_API_KEY and GROK_MODEL must be set")
        self.api_key, self.model = api_key, model
        self.cache = Path(cache_dir) / "script"
        self.cache.mkdir(parents=True, exist_ok=True)
        self.http = http or httpx.Client(timeout=90)
        self.p_in, self.p_out = price_in_per_mtok, price_out_per_mtok

    def cost_usd(self, usage: dict) -> float:
        return (usage.get("prompt_tokens", 0) * self.p_in
                + usage.get("completion_tokens", 0) * self.p_out) / 1e6

    def _call(self, prompt: str) -> tuple[dict, dict]:
        body = {"model": self.model, "temperature": 0.7,
                "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
                "response_format": {"type": "json_schema",
                                    "json_schema": {"name": "narration", "strict": True, "schema": SCHEMA}}}
        r = self.http.post(XAI_URL, json=body, headers={"Authorization": f"Bearer {self.api_key}"})
        if r.status_code >= 400:
            raise ScriptError(f"xAI {r.status_code}: {r.text[:300]}")
        j = r.json()
        try:
            return json.loads(j["choices"][0]["message"]["content"]), j.get("usage", {})
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            raise ScriptError(f"unparseable script reply: {e}") from e

    def write(self, plan: Plan) -> Script:
        prompt = build_prompt(plan)
        f = self.cache / f"{content_hash(self.model, SYSTEM, prompt)}.json"
        if f.exists():
            s = validate(json.loads(f.read_text(encoding="utf-8")), plan)
            s.cached = True
            return s
        usage: dict = {}
        err = None
        for attempt in range(2):
            p = prompt if attempt == 0 else f"{prompt}\n\nYour last reply failed a check: {err}. Fix it."
            raw, u = self._call(p)
            for k, v in u.items():
                if isinstance(v, (int, float)):
                    usage[k] = usage.get(k, 0) + v
            try:
                s = validate(raw, plan)
            except ScriptError as e:
                err = str(e)
                continue
            f.write_text(json.dumps(raw), encoding="utf-8")
            s.usage = usage
            return s
        raise ScriptError(f"script failed checks twice: {err}")
