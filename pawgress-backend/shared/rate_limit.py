"""
shared/rate_limit.py

Pre-deployment security pass (2026-09-13) — login/register had no
brute-force protection at all before this. Deliberately a plain in-memory
fixed-window counter, not a new dependency (e.g. slowapi) and not
Redis-backed:

- No new package to `pip install` — everything here is stdlib, so it
  works the moment this file lands, no environment setup required.
- Matches this codebase's own established pattern (System Architecture
  §15's caching decision, §14's background-jobs decision): don't reach
  for shared/distributed infrastructure before there's a measured reason
  to. A single-process in-memory limiter is honest about being exactly
  that — it resets on restart, and does NOT coordinate across multiple
  backend replicas if this is ever horizontally scaled (System
  Architecture §24 already anticipates stateless replicas eventually;
  when that actually happens, this needs to move to something shared,
  e.g. Redis — that's the revisit trigger for this file specifically).

This is a real, if modest, improvement over "nothing" — it stops the
cheapest, most automatable form of credential-stuffing/brute-force
against a single instance, which is exactly the risk profile of a
pre-launch app with a small number of real users.
"""

import threading
import time
from collections import defaultdict


class InMemoryRateLimiter:
    def __init__(self, max_attempts: int, window_seconds: float):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        """Returns True if this request is within the limit (and records
        it as a hit), False if the caller should be rejected."""
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] < cutoff:
                hits.pop(0)
            if len(hits) >= self.max_attempts:
                return False
            hits.append(now)
            return True

    def reset(self) -> None:
        """Test-only: clears all recorded hits so test order/isolation
        doesn't depend on real wall-clock time passing between tests."""
        with self._lock:
            self._hits.clear()


# Deliberately generous, tunable numbers — not derived from any
# measurement (there's no real traffic yet to measure against), chosen to
# stop obvious automated abuse without making a real user's occasional
# mistyped password an annoyance. Revisit once there's real login/register
# traffic to look at.
login_rate_limiter = InMemoryRateLimiter(max_attempts=10, window_seconds=5 * 60)
register_rate_limiter = InMemoryRateLimiter(max_attempts=5, window_seconds=60 * 60)
password_reset_rate_limiter = InMemoryRateLimiter(max_attempts=5, window_seconds=60 * 60)


def client_ip(request) -> str:
    """Best-effort client identifier. request.client.host is None in some
    test/proxy setups, in which case a shared fallback key means those
    requests share one bucket rather than crashing — acceptable for a
    single-instance MVP deployment; a real production deployment behind a
    load balancer would need to honor X-Forwarded-For instead, which this
    deliberately does not attempt yet (trusting that header blindly
    without knowing the real proxy setup is its own security mistake)."""
    return request.client.host if request.client else "unknown"
