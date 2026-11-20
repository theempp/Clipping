import json

from clipworker.config import DEFAULT_REACTIONS, DetectorParams
from clipworker.detector.dedupe import detection_key, jaccard, same_moment
from clipworker.detector.replay import evaluate, load_twitchdownloader_chat, replay
from clipworker.detector.signals import compile_reactions, reaction_weight, robust_z

from conftest import synth_chat

P = DetectorParams()


def test_reaction_weight_words_and_phrases():
    c = compile_reactions(DEFAULT_REACTIONS)
    assert reaction_weight("KEKW KEKW", c) == 1.0
    assert reaction_weight("bro clip it now", c) == 1.5
    assert reaction_weight("kekw", c) == 1.0
    assert reaction_weight("Lawrence", c) == 0.0        # 'L' must be a whole word
    assert reaction_weight("what ??", c) == 0.6


def test_robust_z_ignores_single_outlier():
    hist = [1.0] * 50 + [100.0]
    assert robust_z(1.0, hist, 0.5) == 0
    assert robust_z(6.0, hist, 0.5) == 10.0


def test_spike_detected_once_with_window():
    msgs = synth_chat(spikes=[(400, 8, 12, "KEKW KEKW")])
    moments, _ = replay(msgs, P, DEFAULT_REACTIONS)
    assert len(moments) == 1
    m = moments[0]
    assert 398 <= m.start_ts <= 406
    assert m.window_start == m.start_ts - 25
    assert m.window_end >= m.start_ts + 15
    assert m.window_end - m.window_start <= 90


def test_quiet_chat_no_triggers():
    moments, _ = replay(synth_chat(seed=7), P, DEFAULT_REACTIONS)
    assert moments == []


def test_single_spammer_does_not_trigger():
    msgs = synth_chat()
    msgs += [(400 + i * 0.05, "spammer", "KEKW") for i in range(200)]
    msgs.sort()
    moments, _ = replay(msgs, P, DEFAULT_REACTIONS)
    assert moments == []


def test_warmup_blocks_early_trigger():
    msgs = synth_chat(spikes=[(20, 8, 12, "KEKW")])
    moments, _ = replay(msgs, P, DEFAULT_REACTIONS)
    assert all(m.start_ts > 60 for m in moments)


def test_cooldown_and_merge():
    # two spikes 10 s apart merge into one moment; a third 3 min later is separate
    msgs = synth_chat(spikes=[(400, 6, 12, "KEKW"), (412, 6, 12, "LUL"), (600, 6, 12, "W")])
    moments, _ = replay(msgs, P, DEFAULT_REACTIONS)
    assert len(moments) == 2
    assert moments[0].last_above_ts >= 412


def test_audio_lifts_borderline_chat():
    msgs = synth_chat(spikes=[(400, 6, 4, "nice")])
    quiet = [(float(t), -30.0 + (t % 3) * 0.5) for t in range(0, 720)]
    loud = [(t, (-12.0 if 399 <= t <= 408 else v)) for t, v in quiet]
    without, _ = replay(msgs, P, DEFAULT_REACTIONS, loudness=quiet)
    with_audio, _ = replay(msgs, P, DEFAULT_REACTIONS, loudness=loud)
    assert len(with_audio) >= len(without)
    assert any(390 <= m.start_ts <= 410 for m in with_audio)


def test_twitchdownloader_load_and_eval(tmp_path):
    msgs = synth_chat(spikes=[(300, 8, 12, "OMEGALUL"), (500, 8, 12, "CLIP IT")])
    doc = {"comments": [{"content_offset_seconds": t, "commenter": {"name": u},
                         "message": {"body": txt}} for t, u, txt in msgs]}
    f = tmp_path / "chat.json"
    f.write_text(json.dumps(doc))
    loaded = load_twitchdownloader_chat(f)
    assert len(loaded) == len(msgs)
    moments, _ = replay(loaded, P, DEFAULT_REACTIONS)
    res = evaluate(moments, [305.0, 505.0, 650.0], loaded[-1][0] - loaded[0][0])
    assert res.caught == 2 and res.labeled == 3
    assert "recall 2/3" in res.summary()


def test_dedupe():
    assert detection_key("twitch:lacy", 105) == detection_key("twitch:lacy", 109)
    a = "no way he just hit that shot from across the map bro"
    b = "he just hit that shot from across the map bro what"
    assert jaccard(a, b) > 0.5
    assert same_moment(100, a, 112, b)
    assert not same_moment(100, a, 200, b)
    assert not same_moment(100, a, 105, "completely different words here today")
