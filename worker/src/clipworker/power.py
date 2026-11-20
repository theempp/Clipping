"""Keep the PC awake only while monitoring (stream-ingest rule 4)."""
from __future__ import annotations

import sys
from contextlib import contextmanager

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


def _set(flags: int) -> bool:
    if sys.platform != "win32":
        return False
    import ctypes
    return bool(ctypes.windll.kernel32.SetThreadExecutionState(flags))


@contextmanager
def keep_awake():
    _set(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
    try:
        yield
    finally:
        _set(ES_CONTINUOUS)
