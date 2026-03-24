"""
Rate Limiter — Project 2
========================
Demonstrates two production-grade rate-limiting algorithms:
  - Token Bucket   : allows configured burst capacity
  - Sliding Window : smooth per-window request limiting

Both implementations are thread-safe.
"""

import threading
import time
from collections import deque


# ---------------------------------------------------------------------------
# Token Bucket Rate Limiter
# ---------------------------------------------------------------------------

class TokenBucketRateLimiter:
    """
    Token Bucket algorithm.

    Tokens are added to the bucket at *refill_rate* tokens per second.
    The bucket holds at most *capacity* tokens.  Each allowed request
    consumes exactly one token.  Requests are rejected when the bucket
    is empty.

    Args:
        capacity:    Maximum number of tokens the bucket can hold (burst size).
        refill_rate: Tokens added per second.

    Example::

        limiter = TokenBucketRateLimiter(capacity=10, refill_rate=2)
        for _ in range(10):
            print(limiter.allow("user-1"))  # True
        print(limiter.allow("user-1"))       # False — bucket empty
    """

    def __init__(self, capacity: float, refill_rate: float) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        if refill_rate <= 0:
            raise ValueError("refill_rate must be positive")
        self._capacity = capacity
        self._refill_rate = refill_rate
        self._buckets: dict[str, dict] = {}
        self._lock = threading.Lock()

    def _get_bucket(self, client_id: str) -> dict:
        if client_id not in self._buckets:
            self._buckets[client_id] = {
                "tokens": self._capacity,
                "last_refill": time.monotonic(),
            }
        return self._buckets[client_id]

    def _refill(self, bucket: dict) -> None:
        now = time.monotonic()
        elapsed = now - bucket["last_refill"]
        new_tokens = elapsed * self._refill_rate
        bucket["tokens"] = min(self._capacity, bucket["tokens"] + new_tokens)
        bucket["last_refill"] = now

    def allow(self, client_id: str) -> bool:
        """Return ``True`` if the request is allowed, ``False`` if rate-limited."""
        with self._lock:
            bucket = self._get_bucket(client_id)
            self._refill(bucket)
            if bucket["tokens"] >= 1:
                bucket["tokens"] -= 1
                return True
            return False

    def available_tokens(self, client_id: str) -> float:
        """Return the current token count for *client_id* (read-only)."""
        with self._lock:
            bucket = self._get_bucket(client_id)
            self._refill(bucket)
            return bucket["tokens"]

    def reset(self, client_id: str) -> None:
        """Reset the bucket for *client_id* to full capacity."""
        with self._lock:
            self._buckets.pop(client_id, None)


# ---------------------------------------------------------------------------
# Sliding Window Counter Rate Limiter
# ---------------------------------------------------------------------------

class SlidingWindowRateLimiter:
    """
    Sliding Window Counter algorithm.

    Keeps a timestamped log of every allowed request.  Before each new
    request, timestamps older than *window_seconds* are discarded.  If
    the remaining count is below *max_requests* the request is allowed.

    This gives a perfectly smooth limit (no burst at window boundary)
    at the cost of O(max_requests) memory per client.

    Args:
        max_requests:    Maximum number of requests permitted per window.
        window_seconds:  Length of the sliding window in seconds.

    Example::

        limiter = SlidingWindowRateLimiter(max_requests=5, window_seconds=1.0)
        for _ in range(5):
            print(limiter.allow("user-1"))  # True
        print(limiter.allow("user-1"))       # False — window full
    """

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        if max_requests <= 0:
            raise ValueError("max_requests must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._logs: dict[str, deque] = {}
        self._lock = threading.Lock()

    def _get_log(self, client_id: str) -> deque:
        if client_id not in self._logs:
            self._logs[client_id] = deque()
        return self._logs[client_id]

    def allow(self, client_id: str) -> bool:
        """Return ``True`` if the request is allowed, ``False`` if rate-limited."""
        with self._lock:
            now = time.monotonic()
            log = self._get_log(client_id)
            cutoff = now - self._window_seconds
            while log and log[0] <= cutoff:
                log.popleft()
            if len(log) < self._max_requests:
                log.append(now)
                return True
            return False

    def current_count(self, client_id: str) -> int:
        """Return the number of requests in the current window for *client_id*."""
        with self._lock:
            now = time.monotonic()
            log = self._get_log(client_id)
            cutoff = now - self._window_seconds
            while log and log[0] <= cutoff:
                log.popleft()
            return len(log)

    def reset(self, client_id: str) -> None:
        """Clear request history for *client_id*."""
        with self._lock:
            self._logs.pop(client_id, None)
