"""Small shared utilities."""

from __future__ import annotations

import time
from typing import Callable, TypeVar

T = TypeVar("T")


def with_retries(fn: Callable[[], T], attempts: int = 3) -> T:
    """Call `fn` with up to `attempts` tries and exponential backoff (1s, 2s, ...)."""
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - retry any transient API/network error
            last_exc = exc
            if attempt < attempts - 1:
                time.sleep(2**attempt)
    assert last_exc is not None
    raise last_exc
