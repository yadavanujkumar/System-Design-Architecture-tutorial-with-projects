"""Tests for the Circuit Breaker implementation."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import threading
import time

import pytest

from circuit_breaker import CircuitBreaker, CircuitBreakerOpenError, CircuitState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def always_succeed(*args, **kwargs):
    return "ok"


def always_fail(*args, **kwargs):
    raise ValueError("downstream error")


def make_breaker(**kwargs):
    """Convenience factory with small defaults suitable for unit tests."""
    defaults = dict(failure_threshold=3, cooldown_seconds=0.1, name="TestCB")
    defaults.update(kwargs)
    return CircuitBreaker(**defaults)


# ---------------------------------------------------------------------------
# Initialisation / validation
# ---------------------------------------------------------------------------

class TestInit:
    def test_defaults(self):
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_threshold == 5
        assert cb.cooldown_seconds == 30.0
        assert cb.success_threshold == 1

    def test_custom_parameters(self):
        cb = CircuitBreaker(failure_threshold=2, cooldown_seconds=1.0, success_threshold=2)
        assert cb.failure_threshold == 2
        assert cb.cooldown_seconds == 1.0
        assert cb.success_threshold == 2

    def test_invalid_failure_threshold_raises(self):
        with pytest.raises(ValueError):
            CircuitBreaker(failure_threshold=0)

    def test_invalid_cooldown_raises(self):
        with pytest.raises(ValueError):
            CircuitBreaker(cooldown_seconds=0)

    def test_invalid_success_threshold_raises(self):
        with pytest.raises(ValueError):
            CircuitBreaker(success_threshold=0)


# ---------------------------------------------------------------------------
# CLOSED state behaviour
# ---------------------------------------------------------------------------

class TestClosedState:
    def test_successful_call_passes_through(self):
        cb = make_breaker()
        assert cb.call(always_succeed) == "ok"
        assert cb.state == CircuitState.CLOSED

    def test_failure_is_recorded(self):
        cb = make_breaker(failure_threshold=3)
        with pytest.raises(ValueError):
            cb.call(always_fail)
        assert cb.failure_count == 1
        assert cb.state == CircuitState.CLOSED

    def test_below_threshold_stays_closed(self):
        cb = make_breaker(failure_threshold=3)
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(always_fail)
        assert cb.state == CircuitState.CLOSED

    def test_reaching_threshold_trips_to_open(self):
        cb = make_breaker(failure_threshold=3)
        for _ in range(3):
            with pytest.raises(ValueError):
                cb.call(always_fail)
        assert cb.state == CircuitState.OPEN

    def test_success_clears_failure_count(self):
        cb = make_breaker(failure_threshold=3)
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(always_fail)
        cb.call(always_succeed)
        # After a success, failures are cleared — 2 more failures should not trip
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(always_fail)
        assert cb.state == CircuitState.CLOSED

    def test_call_passes_args_and_returns_value(self):
        cb = make_breaker()
        result = cb.call(lambda x, y: x + y, 3, 4)
        assert result == 7

    def test_call_passes_kwargs(self):
        cb = make_breaker()
        result = cb.call(lambda x, y=0: x * y, 5, y=3)
        assert result == 15


# ---------------------------------------------------------------------------
# OPEN state behaviour
# ---------------------------------------------------------------------------

class TestOpenState:
    def test_open_circuit_raises_immediately(self):
        cb = make_breaker(failure_threshold=1)
        with pytest.raises(ValueError):
            cb.call(always_fail)
        assert cb.state == CircuitState.OPEN
        with pytest.raises(CircuitBreakerOpenError):
            cb.call(always_succeed)

    def test_open_circuit_does_not_call_downstream(self):
        calls = []

        def track(*args, **kwargs):
            calls.append(1)
            raise RuntimeError("should not be reached")

        cb = make_breaker(failure_threshold=1)
        with pytest.raises(RuntimeError):
            cb.call(track)

        # Now OPEN — next call should not invoke track()
        with pytest.raises(CircuitBreakerOpenError):
            cb.call(track)
        assert len(calls) == 1  # only the first call reached downstream

    def test_open_error_message_contains_name(self):
        cb = make_breaker(failure_threshold=1, name="PaymentService")
        with pytest.raises(ValueError):
            cb.call(always_fail)
        with pytest.raises(CircuitBreakerOpenError, match="PaymentService"):
            cb.call(always_succeed)


# ---------------------------------------------------------------------------
# HALF_OPEN state behaviour
# ---------------------------------------------------------------------------

class TestHalfOpenState:
    def test_transitions_to_half_open_after_cooldown(self):
        cb = make_breaker(failure_threshold=1, cooldown_seconds=0.05)
        with pytest.raises(ValueError):
            cb.call(always_fail)
        assert cb.state == CircuitState.OPEN
        time.sleep(0.1)
        assert cb.state == CircuitState.HALF_OPEN

    def test_successful_probe_resets_to_closed(self):
        cb = make_breaker(failure_threshold=1, cooldown_seconds=0.05)
        with pytest.raises(ValueError):
            cb.call(always_fail)
        time.sleep(0.1)
        assert cb.state == CircuitState.HALF_OPEN
        cb.call(always_succeed)
        assert cb.state == CircuitState.CLOSED

    def test_failed_probe_returns_to_open(self):
        cb = make_breaker(failure_threshold=1, cooldown_seconds=0.05)
        with pytest.raises(ValueError):
            cb.call(always_fail)
        time.sleep(0.1)
        assert cb.state == CircuitState.HALF_OPEN
        with pytest.raises(ValueError):
            cb.call(always_fail)
        assert cb.state == CircuitState.OPEN

    def test_second_probe_blocked_while_first_in_flight(self):
        """Only one probe should be allowed through at a time in HALF_OPEN."""
        cb = make_breaker(failure_threshold=1, cooldown_seconds=0.05)
        with pytest.raises(ValueError):
            cb.call(always_fail)
        time.sleep(0.1)

        barrier = threading.Barrier(2)
        results = []

        def slow_probe():
            # Simulate a slow downstream: hold the lock-free call
            barrier.wait()  # sync with main thread
            time.sleep(0.05)
            return "probe_done"

        t = threading.Thread(target=lambda: results.append(cb.call(slow_probe)))
        t.start()
        barrier.wait()  # ensure slow_probe has passed the state check

        # A second concurrent call should be blocked
        with pytest.raises(CircuitBreakerOpenError):
            cb.call(always_succeed)

        t.join()

    def test_success_threshold_greater_than_one(self):
        cb = make_breaker(
            failure_threshold=1,
            cooldown_seconds=0.05,
            success_threshold=3,
        )
        with pytest.raises(ValueError):
            cb.call(always_fail)
        time.sleep(0.1)

        cb.call(always_succeed)
        assert cb.state == CircuitState.HALF_OPEN  # 1 success, need 3
        cb.call(always_succeed)
        assert cb.state == CircuitState.HALF_OPEN  # 2 successes
        cb.call(always_succeed)
        assert cb.state == CircuitState.CLOSED     # 3 successes → closed


# ---------------------------------------------------------------------------
# Sliding window
# ---------------------------------------------------------------------------

class TestSlidingWindow:
    def test_old_failures_expire_from_window(self):
        cb = CircuitBreaker(
            failure_threshold=3,
            cooldown_seconds=1.0,
            window_seconds=0.15,
            name="WindowCB",
        )
        # Two failures
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(always_fail)
        assert cb.state == CircuitState.CLOSED

        # Wait for those failures to fall outside the window
        time.sleep(0.2)

        # One more failure — total within window is now 1, not 3
        with pytest.raises(ValueError):
            cb.call(always_fail)
        assert cb.state == CircuitState.CLOSED  # not tripped

    def test_failures_within_window_trip_breaker(self):
        cb = CircuitBreaker(
            failure_threshold=3,
            cooldown_seconds=0.1,
            window_seconds=1.0,
            name="WindowCB",
        )
        for _ in range(3):
            with pytest.raises(ValueError):
                cb.call(always_fail)
        assert cb.state == CircuitState.OPEN


# ---------------------------------------------------------------------------
# Manual reset
# ---------------------------------------------------------------------------

class TestReset:
    def test_manual_reset_from_open(self):
        cb = make_breaker(failure_threshold=1)
        with pytest.raises(ValueError):
            cb.call(always_fail)
        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED

    def test_manual_reset_clears_failure_count(self):
        cb = make_breaker(failure_threshold=5)
        for _ in range(4):
            with pytest.raises(ValueError):
                cb.call(always_fail)
        cb.reset()
        assert cb.failure_count == 0

    def test_calls_succeed_after_manual_reset(self):
        cb = make_breaker(failure_threshold=1)
        with pytest.raises(ValueError):
            cb.call(always_fail)
        cb.reset()
        assert cb.call(always_succeed) == "ok"


# ---------------------------------------------------------------------------
# Decorator interface
# ---------------------------------------------------------------------------

class TestDecorator:
    def test_decorator_wraps_function(self):
        cb = make_breaker(failure_threshold=3)

        @cb
        def my_service(x):
            return x * 2

        assert my_service(5) == 10

    def test_decorator_trips_on_failures(self):
        cb = make_breaker(failure_threshold=2)

        @cb
        def flaky():
            raise IOError("network error")

        for _ in range(2):
            with pytest.raises(IOError):
                flaky()

        assert cb.state == CircuitState.OPEN
        with pytest.raises(CircuitBreakerOpenError):
            flaky()

    def test_decorator_preserves_function_name(self):
        cb = make_breaker()

        @cb
        def my_named_function():
            pass

        assert my_named_function.__name__ == "my_named_function"


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_failures_trip_exactly_once(self):
        cb = CircuitBreaker(failure_threshold=10, cooldown_seconds=1.0, name="Concurrent")
        errors = []
        barrier = threading.Barrier(10)

        def fail_concurrently():
            barrier.wait()
            try:
                cb.call(always_fail)
            except (ValueError, CircuitBreakerOpenError) as exc:
                errors.append(type(exc).__name__)

        threads = [threading.Thread(target=fail_concurrently) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert cb.state == CircuitState.OPEN
        assert len(errors) == 10

    def test_concurrent_successful_calls(self):
        cb = make_breaker(failure_threshold=100)
        results = []
        lock = threading.Lock()

        def succeed():
            r = cb.call(always_succeed)
            with lock:
                results.append(r)

        threads = [threading.Thread(target=succeed) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 50
        assert all(r == "ok" for r in results)
        assert cb.state == CircuitState.CLOSED


# ---------------------------------------------------------------------------
# repr
# ---------------------------------------------------------------------------

class TestRepr:
    def test_repr_contains_key_info(self):
        cb = CircuitBreaker(failure_threshold=3, cooldown_seconds=10.0, name="MyService")
        r = repr(cb)
        assert "MyService" in r
        assert "CLOSED" in r
        assert "3" in r
