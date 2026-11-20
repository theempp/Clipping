"""Grok judgment on the shortlist only (text window, never video).

Input: ~40 s transcript, 30-message chat sample, detector scores, campaign
rules summary. Output: strict JSON (keep/drop, category, trim, hook, title,
emphasis words, confidence). Cached by content hash; spend logged.
Model = cheapest that passes the labeled eval set; set GROK_MODEL in .env.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from ..detector.dedupe import content_hash
from ..transcribe import Word

XAI_URL = "https://api.x.ai/v1/chat/completions"
CATEGORIES = ["funny", "clutch", "rage", "wholesome", "fail", "reaction", "drama", "other"]
# Hook types a clip may open on. First three from the clipper-video rubric;
# reaction_peak / play_peak cover stream moments that land without words.
HOOK_TYPES = ["surprising_fact", "bold_claim", "story_start", "reaction_peak", "play_peak", "none"]
HOOK_LEAD_S = 0.15   # start this far before the first hook word
PAYOFF_TAIL_S = 0.35  # end this far after the last payoff word
MIN_SCORE = 6         # score_10 below this is dropped

SYSTEM = (
    "You judge short-form clip candidates from a live stream, like a top Shorts editor.\n"
    "1. Standalone test: keep only moments a total stranger understands with zero context.\n"
    "2. Hook first: trim_in is the exact start of the hook, skipping any ramble before it. "
    "The first 2 seconds must be one of: surprising_fact, bold_claim, story_start, "
    "reaction_peak (big streamer/chat reaction), play_peak (the play itself). "
    "If none fits, hook_type is none.\n"
    "3. End on the payoff: trim_out is just after the payoff lands, so the clip feels finished.\n"
    "4. score_10: 1-10 for how likely a stranger watches to the end and shares. Be strict; "
    "7+ is postable, 9-10 is rare.\n"
    "5. title: punchy, under 60 chars, no clickbait lies. post_caption: one line to post with "
    "the clip, often the best quote. hashtags: 2-3, lowercase, with #.\n"
    "6. emphasis_words: 2-6 words from the transcript that carry the moment (numbers, names, "
    "strong words); they get highlighted in captions.\n"
    "Respect the campaign rules. Times are seconds from window start. "
    "Reply with JSON only, matching the schema."
)

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["keep", "category", "hook_type", "standalone", "score_10", "trim_in",
                 "trim_out", "hook", "title", "post_caption", "hashtags",
                 "emphasis_words", "confidence", "reason"],
    "properties": {
        "keep": {"type": "boolean"},
        "category": {"type": "string", "enum": CATEGORIES},
        "hook_type": {"type": "string", "enum": HOOK_TYPES},
        "standalone": {"type": "boolean"},
        "score_10": {"type": "integer"},
        "trim_in": {"type": "number"},
        "trim_out": {"type": "number"},
        "hook": {"type": "string"},
        "title": {"type": "string"},
        "post_caption": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
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
    hook_type: str = "none"
    standalone: bool = True
    score_10: int = 0
    post_caption: str = ""
    hashtags: list[str] = field(default_factory=list)
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


VERBAL_HOOKS = {"surprising_fact", "bold_claim", "story_start"}


def snap_to_words(t_in: float, t_out: float, words: list[Word],
                  verbal: bool = True) -> tuple[float, float]:
    """Make cuts land on word boundaries. Pure code, no model.

    - Never cut through a word: a cut inside a word moves outward to keep it whole.
    - Verbal hook: start exactly on the first hook word (minus a short lead), so
      dead air before the hook is skipped.
    - Visual hook (reaction/play peak): keep the model's start (the lead-in is the moment).
    - Ending keeps the model's payoff point (a laugh after the last word stays in).
    """
    new_in, new_out = t_in, t_out
    for w in words:
        if w.start < t_in < w.end:
            new_in = w.start
        if w.start < t_out < w.end:
            new_out = min(w.end + PAYOFF_TAIL_S, _next_start(words, w))
    if verbal and new_in == t_in:
        first = next((w for w in words if w.start >= t_in and w.start < t_out), None)
        if first is not None:
            prev_end = max((w.end for w in words if w.end <= first.start), default=0.0)
            new_in = max(prev_end, first.start - HOOK_LEAD_S, t_in)
    return new_in, max(new_in, new_out)


def _next_start(words: list[Word], w: Word) -> float:
    return min((x.start for x in words if x.start >= w.end), default=float("inf"))


def _tags(raw) -> list[str]:
    out = []
    for t in raw or []:
        t = "#" + str(t).strip().lstrip("#").replace(" ", "").lower()
        if len(t) > 1 and t not in out:
            out.append(t[:40])
    return out[:3]


def validate(raw: dict, duration: float, min_len: float, max_len: float,
             words: list[Word] | None = None) -> Judgment:
    base = ["keep", "category", "trim_in", "trim_out", "hook", "title",
            "emphasis_words", "confidence", "reason"]
    missing = [k for k in base if k not in raw]
    if missing:
        raise JudgeError(f"judge output missing {missing}")
    cat = raw["category"] if raw["category"] in CATEGORIES else "other"
    hook_type = raw.get("hook_type", "none")
    hook_type = hook_type if hook_type in HOOK_TYPES else "none"
    standalone = bool(raw.get("standalone", True))
    rubric = "hook_type" in raw  # judgments cached before the rubric skip the new rules
    try:
        score = max(1, min(10, int(round(float(raw["score_10"]))))) if "score_10" in raw else 0
    except (TypeError, ValueError):
        score = 1
    t_in = max(0.0, min(float(raw["trim_in"]), duration))
    t_out = max(t_in, min(float(raw["trim_out"]), duration))
    if words and rubric:
        t_in, t_out = snap_to_words(t_in, t_out, words, hook_type in VERBAL_HOOKS)
        t_in, t_out = max(0.0, t_in), min(duration, t_out)
    if t_out - t_in < min_len:  # widen symmetrically inside the window
        pad = (min_len - (t_out - t_in)) / 2
        t_in, t_out = max(0.0, t_in - pad), min(duration, t_out + pad)
    if t_out - t_in > max_len:
        t_out = t_in + max_len
    conf = max(0.0, min(1.0, float(raw["confidence"])))
    keep, reason = bool(raw["keep"]), str(raw["reason"])[:500]
    # hard rules (code, not model): no hook, not standalone or weak score = drop
    rule = ("no hook in first 2 s" if hook_type == "none" else
            "needs context (fails standalone test)" if not standalone else
            f"score {score}/10 below {MIN_SCORE}" if 0 < score < MIN_SCORE else "")
    if keep and rubric and rule:
        keep, reason = False, f"rule: {rule}; {reason}"[:500]
    return Judgment(keep, cat, round(t_in, 2), round(t_out, 2),
                    str(raw["hook"])[:200], str(raw["title"])[:100],
                    [str(w) for w in raw["emphasis_words"]][:12], conf, reason,
                    hook_type=hook_type, standalone=standalone, score_10=score,
                    post_caption=str(raw.get("post_caption", ""))[:300],
                    hashtags=_tags(raw.get("hashtags")))


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
            j = validate(json.loads(f.read_text(encoding="utf-8")), duration, min_len, max_len, words)
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
        out = validate(raw, duration, min_len, max_len, words)
        f.write_text(json.dumps(raw), encoding="utf-8")
        out.usage = j.get("usage", {})
        return out


    def parse_edit(self, note: str) -> tuple[dict, dict]:
        """(settings, usage). Cached by note hash; one small text call per new note."""
        key = content_hash(self.model, EDIT_SYSTEM, note.strip())
        f = self.cache / f"edit-{key}.json"
        if f.exists():
            return validate_edit(json.loads(f.read_text(encoding="utf-8"))), {}
        body = {"model": self.model, "temperature": 0,
                "messages": [{"role": "system", "content": EDIT_SYSTEM},
                             {"role": "user", "content": note.strip()[:1000]}],
                "response_format": {"type": "json_schema",
                                    "json_schema": {"name": "clip_edit", "strict": True, "schema": EDIT_SCHEMA}}}
        r = self.http.post(XAI_URL, json=body, headers={"Authorization": f"Bearer {self.api_key}"})
        if r.status_code >= 400:
            raise JudgeError(f"xAI {r.status_code}: {r.text[:300]}")
        j = r.json()
        try:
            raw = json.loads(j["choices"][0]["message"]["content"])
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            raise JudgeError(f"unparseable edit reply: {e}") from e
        f.write_text(json.dumps(raw), encoding="utf-8")
        return validate_edit(raw), j.get("usage", {})

# --- plain-English revision box (P4) -------------------------------------------------

EDIT_SYSTEM = (
    "Turn a reviewer's plain-English edit request for a short vertical clip into settings. "
    "Use null for anything the request does not mention. max_len_s: maximum clip length in "
    "seconds. sfx: sound effects on/off. zoom: punch-in zooms on/off. caption_colour: the "
    "caption highlight colour as #RRGGBB (blue = #2F80FF, red = #FF3B30, yellow = #FFD60A, "
    "green = #34C759, purple = #AF52DE, pink = #FF5FA2, orange = #FF9500, white = #FFFFFF). "
    "best_part_only: true when they ask for only the best/strongest part. title: new title or null. "
    "Reply with JSON only."
)

EDIT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["max_len_s", "sfx", "zoom", "caption_colour", "best_part_only", "title"],
    "properties": {
        "max_len_s": {"type": ["number", "null"]},
        "sfx": {"type": ["boolean", "null"]},
        "zoom": {"type": ["boolean", "null"]},
        "caption_colour": {"type": ["string", "null"]},
        "best_part_only": {"type": ["boolean", "null"]},
        "title": {"type": ["string", "null"]},
    },
}


def validate_edit(raw: dict) -> dict:
    """Keep only well-formed, mentioned settings."""
    out: dict = {}
    v = raw.get("max_len_s")
    if isinstance(v, (int, float)) and 3 <= v <= 180:
        out["max_len_s"] = float(v)
    for k in ("sfx", "zoom", "best_part_only"):
        if isinstance(raw.get(k), bool):
            out[k] = raw[k]
    c = raw.get("caption_colour")
    if isinstance(c, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", c.strip()):
        out["caption_colour"] = c.strip().upper()
    t = raw.get("title")
    if isinstance(t, str) and t.strip():
        out["title"] = t.strip()[:100]
    return out
