"""In-memory per-token token-bucket rate limiter."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field


@dataclass
class _Bucket:
    capacity: float
    refill_per_second: float
    tokens: float
    last: float = field(default_factory=time.monotonic)


class RateLimiter:
    def __init__(self, per_minute: int) -> None:
        self._capacity = float(per_minute)
        self._refill = float(per_minute) / 60.0
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        with self._lock:
            b = self._buckets.get(key)
            now = time.monotonic()
            if b is None:
                b = _Bucket(capacity=self._capacity, refill_per_second=self._refill, tokens=self._capacity, last=now)
                self._buckets[key] = b
            elapsed = now - b.last
            b.tokens = min(b.capacity, b.tokens + elapsed * b.refill_per_second)
            b.last = now
            if b.tokens >= 1.0:
                b.tokens -= 1.0
                return True
            return False
