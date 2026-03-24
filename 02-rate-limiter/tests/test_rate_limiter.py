"""Tests for the Rate Limiter implementations."""

import time
import threading
import pytest

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from rate_limiter import TokenBucketRateLimiter, SlidingWindowRateLimiter


# ---------------------------------------------------------------------------
# Token Bucket tests
# ---------------------------------------------------------------------------

class TestTokenBucket:
    def test_allows_requests_up_to_capacity(self):
        limiter = TokenBucketRateLimiter(capacity=5, refill_rate=1)
        results = [limiter.allow("user") for _ in range(5)]
        assert all(results)

    def test_rejects_when_bucket_empty(self):
        limiter = TokenBucketRateLimiter(capacity=3, refill_rate=1)
        for _ in range(3):
            limiter.allow("user")
        assert limiter.allow("user") is False

    def test_refills_over_time(self):
        limiter = TokenBucketRateLimiter(capacity=2, refill_rate=100)
        limiter.allow("user")
        limiter.allow("user")
        assert limiter.allow("user") is False
        time.sleep(0.02)  # 100 tokens/s * 0.02s = 2 new tokens
        assert limiter.allow("user") is True

    def test_different_clients_independent(self):
        limiter = TokenBucketRateLimiter(capacity=1, refill_rate=1)
        assert limiter.allow("a") is True
        assert limiter.allow("b") is True  # separate bucket
        assert limiter.allow("a") is False

    def test_available_tokens_full_bucket(self):
        limiter = TokenBucketRateLimiter(capacity=10, refill_rate=1)
        assert limiter.available_tokens("user") == 10.0

    def test_available_tokens_decreases_after_allow(self):
        limiter = TokenBucketRateLimiter(capacity=10, refill_rate=0.001)
        limiter.allow("user")
        assert limiter.available_tokens("user") < 10.0

    def test_reset_restores_full_capacity(self):
        limiter = TokenBucketRateLimiter(capacity=2, refill_rate=1)
        limiter.allow("user")
        limiter.allow("user")
        assert limiter.allow("user") is False
        limiter.reset("user")
        assert limiter.allow("user") is True

    def test_invalid_capacity_raises(self):
        with pytest.raises(ValueError):
            TokenBucketRateLimiter(capacity=0, refill_rate=1)

    def test_invalid_refill_rate_raises(self):
        with pytest.raises(ValueError):
            TokenBucketRateLimiter(capacity=5, refill_rate=0)

    def test_thread_safe(self):
        limiter = TokenBucketRateLimiter(capacity=50, refill_rate=0.001)
        allowed = []
        lock = threading.Lock()

        def make_requests():
            for _ in range(10):
                result = limiter.allow("shared")
                with lock:
                    allowed.append(result)

        threads = [threading.Thread(target=make_requests) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert sum(allowed) == 50  # exactly 50 allowed, 50 rejected


# ---------------------------------------------------------------------------
# Sliding Window tests
# ---------------------------------------------------------------------------

class TestSlidingWindow:
    def test_allows_requests_up_to_limit(self):
        limiter = SlidingWindowRateLimiter(max_requests=5, window_seconds=10)
        results = [limiter.allow("user") for _ in range(5)]
        assert all(results)

    def test_rejects_over_limit(self):
        limiter = SlidingWindowRateLimiter(max_requests=3, window_seconds=10)
        for _ in range(3):
            limiter.allow("user")
        assert limiter.allow("user") is False

    def test_allows_after_window_expires(self):
        limiter = SlidingWindowRateLimiter(max_requests=2, window_seconds=0.05)
        limiter.allow("user")
        limiter.allow("user")
        assert limiter.allow("user") is False
        time.sleep(0.06)
        assert limiter.allow("user") is True

    def test_different_clients_independent(self):
        limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=10)
        assert limiter.allow("a") is True
        assert limiter.allow("b") is True
        assert limiter.allow("a") is False

    def test_current_count(self):
        limiter = SlidingWindowRateLimiter(max_requests=5, window_seconds=10)
        limiter.allow("user")
        limiter.allow("user")
        assert limiter.current_count("user") == 2

    def test_current_count_zero_initially(self):
        limiter = SlidingWindowRateLimiter(max_requests=5, window_seconds=10)
        assert limiter.current_count("user") == 0

    def test_reset_clears_history(self):
        limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=10)
        limiter.allow("user")
        assert limiter.allow("user") is False
        limiter.reset("user")
        assert limiter.allow("user") is True

    def test_invalid_max_requests_raises(self):
        with pytest.raises(ValueError):
            SlidingWindowRateLimiter(max_requests=0, window_seconds=1)

    def test_invalid_window_raises(self):
        with pytest.raises(ValueError):
            SlidingWindowRateLimiter(max_requests=5, window_seconds=0)

    def test_thread_safe(self):
        limiter = SlidingWindowRateLimiter(max_requests=50, window_seconds=60)
        allowed = []
        lock = threading.Lock()

        def make_requests():
            for _ in range(10):
                result = limiter.allow("shared")
                with lock:
                    allowed.append(result)

        threads = [threading.Thread(target=make_requests) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert sum(allowed) == 50
