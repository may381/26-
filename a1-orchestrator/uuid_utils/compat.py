"""``uuid_utils.compat`` subset used by LangChain / LangSmith."""

from . import uuid7 as _uuid7

from . import uuid1, uuid3, uuid4, uuid5  # noqa: F401  (parity with the wheel)


def uuid7(timestamp=None, nanos=None):  # noqa: F811
    return _uuid7(timestamp=timestamp, nanos=nanos)


__all__ = ["uuid7", "uuid1", "uuid3", "uuid4", "uuid5"]
