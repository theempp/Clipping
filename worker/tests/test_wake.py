"""Dashboard Wake Up switch (D055): the worker watches streams only while it is on."""
from clipworker.config import Settings
from clipworker.live import LiveRunner


class WakeSB:
    def __init__(self, value):
        self.value = value

    def awake(self):
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


class Cap:
    def __init__(self):
        self.stopped = False

    def stop(self):
        self.stopped = True

    def alive(self):
        return not self.stopped


def runner(tmp_path, sb):
    return LiveRunner(Settings(work_dir=tmp_path, channels=[], caption_style=None), None, None, supabase=sb)


def test_offline_run_stays_awake(tmp_path):
    assert runner(tmp_path, None).awake is True


def test_switch_controls_watching(tmp_path):
    sb = WakeSB(False)
    r = runner(tmp_path, sb)
    assert r.awake is False                      # asleep until the dashboard says otherwise
    sb.value = True
    r.sync_awake()
    assert r.awake is True
    cap = Cap()
    r.live, r.caps = {"twitch:lacy"}, {"twitch:lacy": cap}
    sb.value = False
    r.sync_awake()
    assert r.awake is False and r.live == set() and cap.stopped and r.caps == {}


def test_read_errors_keep_last_value(tmp_path):
    sb = WakeSB(True)
    r = runner(tmp_path, sb)
    r.sync_awake()
    sb.value = RuntimeError("network down")
    r.sync_awake()
    assert r.awake is True
    sb.value = None                               # control row missing
    r.sync_awake()
    assert r.awake is True
