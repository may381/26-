"""Pure-Python fallback for the ``uuid_utils`` wheel.

Windows Smart App Control blocks the compiled ``_uuid_utils.pyd`` on this
machine.  LangChain only needs ``uuid7`` for trace IDs, so this package
provides an RFC 9562 implementation and shadows the blocked wheel for the
A1 processes (their working directory / ``sys.path`` contains this folder).
"""

from __future__ import annotations

import os
import threading
import time
import uuid as _uuid

__version__ = "0.0.0-pure-python"

UUID = _uuid.UUID
uuid1 = _uuid.uuid1
uuid3 = _uuid.uuid3
uuid4 = _uuid.uuid4
uuid5 = _uuid.uuid5

_lock = threading.Lock()
_last_ms = 0
_seq = 0


def uuid7(timestamp=None, nanos=None):
    """Return a UUIDv7, optionally for a given Unix time."""
    global _last_ms, _seq
    if timestamp is None:
        now_ns = time.time_ns()
    else:
        now_ns = int(timestamp) * 1_000_000_000 + int(nanos or 0)
    ms = now_ns // 1_000_000
    with _lock:
        if ms > _last_ms:
            _last_ms = ms
            _seq = int.from_bytes(os.urandom(2), "big") & 0x0FFF
        else:
            ms = _last_ms
            _seq += 1
            if _seq > 0x0FFF:
                _last_ms = ms + 1
                ms = _last_ms
                _seq = 0
    rand = int.from_bytes(os.urandom(8), "big") & ((1 << 62) - 1)
    value = (
        ((ms & ((1 << 48) - 1)) << 80)
        | (0x7 << 76)
        | ((_seq & 0x0FFF) << 64)
        | (0b10 << 62)
        | rand
    )
    return _uuid.UUID(int=value)


__all__ = ["uuid7", "uuid1", "uuid3", "uuid4", "uuid5", "UUID"]
