"""Tests for app/web/rate_limit.py"""

import pytest

from app.web.rate_limit import Limit, SlidingWindow, client_key


class Clock:
    """A hand-wound clock, so the tests need not sleep."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def window(requests=3, per_seconds=60.0, **kwargs):
    clock = Clock()
    return SlidingWindow(Limit(requests, per_seconds), clock=clock, **kwargs), clock


# ── Counting ──────────────────────────────────────────────────────

def test_requests_within_the_allowance_pass():
    limiter, _ = window(requests=3)
    assert [limiter.retry_after("a") for _ in range(3)] == [None, None, None]

def test_the_request_over_the_allowance_is_held():
    limiter, _ = window(requests=3)
    for _ in range(3):
        limiter.retry_after("a")
    assert limiter.retry_after("a") is not None

def test_the_wait_counts_down_to_the_window_edge():
    limiter, clock = window(requests=1, per_seconds=60.0)
    limiter.retry_after("a")

    clock.advance(20)
    assert limiter.retry_after("a") == pytest.approx(40.0)

def test_the_allowance_returns_once_the_window_passes():
    limiter, clock = window(requests=2, per_seconds=60.0)
    limiter.retry_after("a")
    limiter.retry_after("a")

    clock.advance(61)
    assert limiter.retry_after("a") is None

def test_it_slides_rather_than_resetting_in_blocks():
    """A fixed window would let twice the allowance through at its edge."""
    limiter, clock = window(requests=2, per_seconds=60.0)
    limiter.retry_after("a")
    clock.advance(59)
    limiter.retry_after("a")

    clock.advance(2)  # the first hit has aged out, the second has not
    assert limiter.retry_after("a") is None
    assert limiter.retry_after("a") is not None

def test_a_blocked_request_is_not_counted():
    """Otherwise a caller who keeps trying would extend their own timeout."""
    limiter, clock = window(requests=1, per_seconds=60.0)
    limiter.retry_after("a")

    clock.advance(30)
    for _ in range(5):
        limiter.retry_after("a")

    clock.advance(31)
    assert limiter.retry_after("a") is None


# ── Keys ──────────────────────────────────────────────────────────

def test_keys_are_counted_separately():
    limiter, _ = window(requests=1)
    assert limiter.retry_after("a") is None
    assert limiter.retry_after("b") is None

def test_one_key_cannot_exhaust_another():
    limiter, _ = window(requests=1)
    limiter.retry_after("a")
    limiter.retry_after("a")
    assert limiter.retry_after("b") is None

def test_the_empty_key_gives_a_global_count():
    limiter, _ = window(requests=2)
    assert limiter.retry_after() is None
    assert limiter.retry_after() is None
    assert limiter.retry_after() is not None


# ── Memory ────────────────────────────────────────────────────────

def test_tracking_is_capped():
    """A stream of fresh keys must not grow memory without bound."""
    limiter, _ = window(requests=5, max_keys=10)
    for i in range(500):
        limiter.retry_after(f"client-{i}")

    assert len(limiter._seen) <= 10

def test_the_least_recently_seen_key_is_dropped_first():
    limiter, _ = window(requests=5, max_keys=2)
    limiter.retry_after("old")
    limiter.retry_after("new")
    limiter.retry_after("newer")

    assert "old" not in limiter._seen
    assert "newer" in limiter._seen


# ── client_key ────────────────────────────────────────────────────

def test_cloudflare_header_wins():
    key = client_key({"cf-connecting-ip": "203.0.113.5", "x-forwarded-for": "10.0.0.1"}, "127.0.0.1")
    assert key == "203.0.113.5"

def test_forwarded_for_is_used_when_cloudflare_is_absent():
    assert client_key({"x-forwarded-for": "203.0.113.5"}, "127.0.0.1") == "203.0.113.5"

def test_only_the_first_forwarded_address_counts():
    """The rest of the chain is appended by intermediaries and not the caller."""
    assert client_key({"x-forwarded-for": "203.0.113.5, 10.0.0.1"}, None) == "203.0.113.5"

def test_the_peer_is_used_without_any_header():
    assert client_key({}, "198.51.100.7") == "198.51.100.7"

def test_an_unknown_caller_still_gets_a_key():
    assert client_key({}, None) == "unknown"
