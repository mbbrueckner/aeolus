"""Request limiting, to keep the upstream forecast quota from being drained.

Two limits apply, and they guard against different things.

A **per-client** limit stops one browser stuck in a refresh loop, which is the
common accident. It is keyed on the client address, which behind a proxy comes
from a header and is therefore only as trustworthy as the proxy in front — a
determined caller can vary it.

A **global** limit is what actually protects the quota. It does not care who is
asking, so it holds even when the per-client key can be forged, and equally when
the traffic is simply real and there is a lot of it.

State is in memory and per process, which suits a single container. Behind
several replicas each would keep its own count, so the global limit would need
to be divided between them or moved to shared storage.
"""

__author__ = "mbbrueckner"
__version__ = "1.0.0"

import threading
import time
from collections import OrderedDict, deque
from dataclasses import dataclass


@dataclass(frozen=True)
class Limit:
    """How many requests are allowed over how long.

    Attributes:
        requests: Number of requests permitted within the window.
        per_seconds: Length of the window in seconds.
    """

    requests: int
    per_seconds: float


class SlidingWindow:
    """Counts requests per key over a moving time window.

    Tracking is capped at ``max_keys`` and evicts the least recently seen, so a
    stream of distinct keys cannot grow memory without bound — which would turn
    the limiter itself into the vulnerability it is meant to close.
    """

    def __init__(self, limit: Limit, max_keys: int = 4096, clock=time.monotonic) -> None:
        """Create a limiter.

        Args:
            limit: The allowance to enforce.
            max_keys: How many distinct keys to remember at once.
            clock: Source of monotonic time, for testing.
        """
        self._limit = limit
        self._max_keys = max_keys
        self._clock = clock
        self._seen: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = threading.Lock()

    def retry_after(self, key: str = "") -> float | None:
        """Register a request and report whether it must wait.

        Args:
            key: Identifier to count against, empty for a global count.

        Returns:
            Seconds until the request would be allowed, or None if it is
            allowed now and has been counted.
        """
        now = self._clock()
        cutoff = now - self._limit.per_seconds

        with self._lock:
            hits = self._seen.get(key)
            if hits is None:
                hits = deque()
                self._seen[key] = hits
            self._seen.move_to_end(key)

            while hits and hits[0] <= cutoff:
                hits.popleft()

            if len(hits) >= self._limit.requests:
                return max(0.0, hits[0] + self._limit.per_seconds - now)

            hits.append(now)
            self._evict()
            return None

    def clear(self) -> None:
        """Forget every key, as between test cases."""
        with self._lock:
            self._seen.clear()

    def _evict(self) -> None:
        """Drop the least recently used keys once the table is full."""
        while len(self._seen) > self._max_keys:
            self._seen.popitem(last=False)


def client_key(headers, peer: str | None) -> str:
    """Identify the caller for per-client counting.

    Behind Cloudflare the real address arrives in ``CF-Connecting-IP``. Both it
    and ``X-Forwarded-For`` are set by whatever sits in front, so neither proves
    anything on its own — see the module docstring for why that is tolerable.

    Args:
        headers: The request headers.
        peer: The address of the immediate connection, if known.

    Returns:
        A key to count against.
    """
    forwarded = headers.get("cf-connecting-ip") or headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return peer or "unknown"
