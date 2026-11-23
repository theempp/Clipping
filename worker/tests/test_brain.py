"""Streamer Brain sliders -> detector weights (D089/D099)."""
from clipworker.config import DetectorParams
from clipworker.detector.brain import DEFAULTS, apply_brain
from clipworker.detector.signals import compile_reactions, reaction_weight
from clipworker.detector.spike import SpikeDetector

BASE = DetectorParams()


def test_untouched_brain_changes_nothing():
    assert apply_brain(BASE, {"KEKW": 1.0}, None, None) == (BASE, {"KEKW": 1.0})
    assert apply_brain(BASE, {}, dict(DEFAULTS), [])[0] == BASE


def test_sliders_scale_weights_and_clamp():
    p, _ = apply_brain(BASE, {}, {"chat_spike": 140, "voice_peak": 0, "chat_words": "x"}, None)
    assert abs(p.w_chat - BASE.w_chat * 2) < 1e-9 and abs(p.w_unique - BASE.w_unique * 2) < 1e-9
    assert p.w_audio == 0 and p.w_reaction == BASE.w_reaction
    p, _ = apply_brain(BASE, {}, {"chat_spike": 1000}, None)
    assert abs(p.w_chat - BASE.w_chat * 2) < 1e-9            # capped at 2x


def test_words_join_the_reaction_list():
    _, r = apply_brain(BASE, {"KEKW": 1.0, "W": 0.5}, None, ["w", "  ", "insane play"])
    assert r["W"] == 1.0 and r["INSANE PLAY"] == 1.0 and r["KEKW"] == 1.0
    assert reaction_weight("that was an INSANE PLAY", compile_reactions(r)) == 1.0


def test_retune_keeps_baseline():
    d = SpikeDetector("twitch:x", BASE, {})
    for i in range(30):
        d.add_message(float(i), f"u{i}", "hi")
        d.tick(float(i))
    n = len(d._h_rate)
    p, r = apply_brain(BASE, {}, {"chat_spike": 35}, ["gg"])
    d.retune(p, r)
    assert len(d._h_rate) == n and d.p.w_chat == BASE.w_chat / 2


class _SB:
    def select(self, table, **_):
        return {"streamers": [{"id": "s1", "slug": "lacy"}],
                "streamer_brain": [{"streamer_id": "s1", "weights": {"voice_peak": 110}, "words": ["clutch"],
                                    "updated_at": "t"}]}[table]


def test_live_runner_applies_brain_per_streamer():
    from types import SimpleNamespace
    from clipworker.live import LiveRunner
    from clipworker.config import Channel
    ch = [Channel("twitch:lacy", "twitch", "lacy", "lacy", None, {}, BASE, "core", 1.0, "Lacy"),
          Channel("twitch:other", "twitch", "other", "other", None, {}, BASE, "core", 1.0, "Other")]
    run = LiveRunner.__new__(LiveRunner)
    run.s, run.sb = SimpleNamespace(channels=ch), _SB()
    run.det = {c.key: SpikeDetector(c.key, c.detector, {}) for c in ch}
    run.sync_brain()
    assert abs(run.det["twitch:lacy"].p.w_audio - BASE.w_audio * 2) < 1e-9
    assert run.det["twitch:other"].p == BASE
    assert "CLUTCH" in run.det["twitch:lacy"].reactions[0]
