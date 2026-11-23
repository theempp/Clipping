"""Always on (D116, supersedes the D055 Wake Up switch): no dashboard switch gates watching."""
from clipworker.config import Settings
from clipworker.live import LiveRunner


class SB:
    """A Supabase stand-in whose control row says asleep: the worker must ignore it."""
    def awake(self):
        return False


def runner(tmp_path, sb):
    return LiveRunner(Settings(work_dir=tmp_path, channels=[], caption_style=None), None, None, supabase=sb)


def test_offline_run_is_on(tmp_path):
    assert runner(tmp_path, None).awake is True


def test_supabase_run_is_on_without_a_switch(tmp_path):
    r = runner(tmp_path, SB())
    assert r.awake is True
    assert not hasattr(r, "sync_awake")
