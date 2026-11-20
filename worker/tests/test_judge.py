import json

import httpx
import pytest

from clipworker.judge.grok import GrokJudge, JudgeError, build_user_prompt, validate
from clipworker.transcribe import CachedTranscriber, Word

RAW = {"keep": True, "category": "funny", "trim_in": 5, "trim_out": 33, "hook": "he did WHAT",
       "title": "No way", "emphasis_words": ["WHAT"], "confidence": 0.8, "reason": "clear payoff"}


def _client(calls, raw=RAW, status=200):
    def handler(req):
        calls.append(json.loads(req.content))
        if status != 200:
            return httpx.Response(status, text="boom")
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(raw)}}],
                                         "usage": {"prompt_tokens": 1000, "completion_tokens": 100,
                                                   "total_tokens": 1100}})
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_validate_clamps_to_window_and_campaign():
    j = validate({**RAW, "trim_in": -4, "trim_out": 500, "category": "weird", "confidence": 3},
                 duration=40, min_len=10, max_len=30)
    assert (j.trim_in, j.trim_out) == (0.0, 30.0)
    assert j.category == "other" and j.confidence == 1.0
    j = validate({**RAW, "trim_in": 20, "trim_out": 22}, duration=40, min_len=10, max_len=60)
    assert j.trim_out - j.trim_in == pytest.approx(10)
    with pytest.raises(JudgeError):
        validate({"keep": True}, 40, 10, 60)


def test_prompt_is_text_only_and_bounded():
    words = [Word(i * 0.5, i * 0.5 + 0.4, "w") for i in range(80)]
    p = build_user_prompt(words, [f"m{i}" for i in range(100)], {"score": 3.21}, "", 40)
    assert p.count("\nm") <= 30 and "score=3.21" in p and "[0.0]w" in p


def test_judge_calls_once_then_caches(tmp_path):
    calls = []
    g = GrokJudge("k", "grok-test", tmp_path, _client(calls), price_in_per_mtok=0.2, price_out_per_mtok=0.5)
    words = [Word(1, 1.3, "hello")]
    a = g.judge(words, ["KEKW"], {"score": 3}, "", 40)
    b = g.judge(words, ["KEKW"], {"score": 3}, "", 40)
    assert len(calls) == 1 and not a.cached and b.cached
    assert calls[0]["response_format"]["type"] == "json_schema"
    assert g.cost_usd(a.usage) == pytest.approx(0.00025)


def test_judge_http_error(tmp_path):
    g = GrokJudge("k", "m", tmp_path, _client([], status=500))
    with pytest.raises(JudgeError):
        g.judge([], [], {}, "", 40)


def test_judge_requires_config(tmp_path):
    with pytest.raises(JudgeError):
        GrokJudge("", "", tmp_path)


def test_transcriber_cache(tmp_path):
    class Fake:
        n = 0
        def transcribe(self, wav):
            Fake.n += 1
            return [Word(0, 0.5, "hi")]
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFF....")
    t = CachedTranscriber(Fake(), tmp_path)
    assert t.transcribe(wav) == t.transcribe(wav) == [Word(0, 0.5, "hi")]
    assert Fake.n == 1


RUBRIC = {**RAW, "hook_type": "bold_claim", "standalone": True, "score_10": 8,
          "post_caption": "he really said that", "hashtags": ["Lacy", "#fortnite", "x", "y"]}
TALK = [Word(2.0, 2.4, "um"), Word(2.5, 2.8, "so"), Word(6.0, 6.3, "nobody"), Word(6.3, 6.7, "beats"),
        Word(6.7, 7.0, "me"), Word(20.0, 20.6, "EVER"), Word(25.0, 25.3, "next")]


def test_rubric_fields_and_hashtag_cleanup():
    j = validate(RUBRIC, 40, 10, 60)
    assert (j.hook_type, j.standalone, j.score_10) == ("bold_claim", True, 8)
    assert j.hashtags == ["#lacy", "#fortnite", "#x"] and j.post_caption == "he really said that"


@pytest.mark.parametrize("patch,frag", [({"hook_type": "none"}, "no hook"),
                                         ({"standalone": False}, "standalone"),
                                         ({"score_10": 4}, "score 4/10")])
def test_hard_rules_drop(patch, frag):
    j = validate({**RUBRIC, **patch}, 40, 10, 60)
    assert not j.keep and frag in j.reason


def test_legacy_judgment_without_rubric_still_kept():
    j = validate(RAW, 40, 10, 60, TALK)
    assert j.keep and j.score_10 == 0 and (j.trim_in, j.trim_out) == (5.0, 33.0)  # no snapping


def test_verbal_hook_snaps_to_first_word_and_never_cuts_words():
    # model starts in dead air at 3.0 and ends inside "EVER"
    j = validate({**RUBRIC, "trim_in": 3.0, "trim_out": 20.3}, 40, 10, 60, TALK)
    assert j.trim_in == pytest.approx(5.85)          # 0.15 s before "nobody"
    assert j.trim_out == pytest.approx(20.95)        # whole "EVER" + payoff tail


def test_visual_hook_keeps_lead_in():
    j = validate({**RUBRIC, "hook_type": "play_peak", "trim_in": 3.0, "trim_out": 22}, 40, 10, 60, TALK)
    assert (j.trim_in, j.trim_out) == (3.0, 22.0)
    j = validate({**RUBRIC, "hook_type": "play_peak", "trim_in": 2.6, "trim_out": 22}, 40, 10, 60, TALK)
    assert j.trim_in == 2.5                           # cut inside "so" moves to its start


def test_schema_requires_rubric_fields():
    from clipworker.judge.grok import SCHEMA
    for k in ("hook_type", "standalone", "score_10", "post_caption", "hashtags"):
        assert k in SCHEMA["required"] and k in SCHEMA["properties"]
