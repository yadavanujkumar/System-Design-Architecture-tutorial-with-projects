"""
Circuit Breaker Pattern
=======================
Prevents cascading failures in distributed systems by temporarily stopping
calls to a failing downstream service.

States
------
CLOSED  — normal operation; requests pass through; failures are counted.
OPEN    — downstream service is deemed unhealthy; requests fail fast
          (no actual call is made) for ``cooldown_seconds``.
HALF_OPEN — after the cooldown, a single probe request is allowed through.
            If it succeeds, the breaker resets to CLOSED.
            If it fails, it returns to OPEN and restarts the cooldown.

Inspired by Netflix Hystrix and the original pattern described in
Michael Nygard's "Release It!" (2007).
"""

import threading
import time
from enum import Enum
from typing import Any, Callable, Optional


class CircuitState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreakerOpenError(Exception):
    """Raised when a call is attempted while the circuit is OPEN."""


class CircuitBreaker:
    """
    A thread-safe circuit breaker.

    Parameters
    ----------
    failure_threshold : int
        Number of consecutive failures (within ``window_seconds``) required
        to trip the circuit from CLOSED → OPEN.
    cooldown_seconds : float
        How long to stay OPEN before moving to HALF_OPEN.
    success_threshold : int
        Number of consecutive successes in HALF_OPEN required to reset to
        CLOSED.  Defaults to 1 (a single successful probe is enough).
    window_seconds : float
        Sliding time window over which failures are counted.  A failure
        older than this is no longer counted against the threshold.
        Set to ``None`` to count all failures since the last reset (no
        window).
    name : str
        Optional human-readable label (used in ``__repr__`` and errors).
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        cooldown_seconds: float = 30.0,
        success_threshold: int = 1,
        window_seconds: Optional[float] = None,
        name: str = "CircuitBreaker",
    ) -> None:
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        if cooldown_seconds <= 0:
            raise ValueError("cooldown_seconds must be > 0")
        if success_threshold < 1:
            raise ValueError("success_threshold must be >= 1")

        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.success_threshold = success_threshold
        self.window_seconds = window_seconds
        self.name = name

        self._lock = threading.Lock()
        self._reset()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """
        Execute *func* through the circuit breaker.

        Raises
        ------
        CircuitBreakerOpenError
            If the circuit is currently OPEN.
        Exception
            Any exception raised by *func* itself (also recorded as a
            failure).
        """
        with self._lock:
            self._maybe_transition_to_half_open()

            if self._state == CircuitState.OPEN:
                raise CircuitBreakerOpenError(
                    f"[{self.name}] Circuit is OPEN — call blocked. "
                    f"Retry after {self._seconds_until_retry():.1f}s."
                )

            if self._state == CircuitState.HALF_OPEN:
                # Only one probe is allowed through at a time.
                if self._half_open_probe_in_flight:
                    raise CircuitBreakerOpenError(
                        f"[{self.name}] Circuit is HALF_OPEN — probe already "
                        "in flight; subsequent calls blocked."
                    )
                self._half_open_probe_in_flight = True

        # Execute outside the lock so other threads can read state.
        try:
            result = func(*args, **kwargs)
        except Exception:
            with self._lock:
                self._record_failure()
            raise

        with self._lock:
            self._record_success()

        return result

    def reset(self) -> None:
        """Manually reset the circuit to CLOSED state."""
        with self._lock:
            self._reset()

    # ------------------------------------------------------------------
    # Properties (thread-safe reads)
    # ------------------------------------------------------------------

    @property
    def state(self) -> CircuitState:
        with self._lock:
            self._maybe_transition_to_half_open()
            return self._state

    @property
    def failure_count(self) -> int:
        with self._lock:
            return self._current_failure_count()

    @property
    def success_count(self) -> int:
        """Consecutive successes recorded in HALF_OPEN state."""
        with self._lock:
            return self._consecutive_successes

    # ------------------------------------------------------------------
    # Internal helpers  (must be called while holding ``_lock``)
    # ------------------------------------------------------------------

    def _reset(self) -> None:
        self._state = CircuitState.CLOSED
        self._failure_timestamps: list[float] = []
        self._consecutive_failures: int = 0
        self._consecutive_successes: int = 0
        self._opened_at: Optional[float] = None
        self._half_open_probe_in_flight: bool = False

    def _current_failure_count(self) -> int:
        """Return the number of failures within the current window."""
        if self.window_seconds is None:
            return self._consecutive_failures
        cutoff = time.monotonic() - self.window_seconds
        # Prune old failures.
        self._failure_timestamps = [
            t for t in self._failure_timestamps if t >= cutoff
        ]
        return len(self._failure_timestamps)

    def _record_failure(self) -> None:
        now = time.monotonic()
        self._failure_timestamps.append(now)
        self._consecutive_failures += 1
        self._consecutive_successes = 0
        self._half_open_probe_in_flight = False

        if self._state == CircuitState.HALF_OPEN:
            # Probe failed → go back to OPEN.
            self._trip(now)
            return

        if self._current_failure_count() >= self.failure_threshold:
            self._trip(now)

    def _record_success(self) -> None:
        self._consecutive_failures = 0
        self._consecutive_successes += 1
        self._half_open_probe_in_flight = False

        if self._state == CircuitState.HALF_OPEN:
            if self._consecutive_successes >= self.success_threshold:
                self._reset()  # Back to CLOSED.
        else:
            # In CLOSED state a success just clears consecutive failure count.
            self._failure_timestamps.clear()

    def _trip(self, now: float) -> None:
        self._state = CircuitState.OPEN
        self._opened_at = now

    def _maybe_transition_to_half_open(self) -> None:
        if (
            self._state == CircuitState.OPEN
            and self._opened_at is not None
            and time.monotonic() - self._opened_at >= self.cooldown_seconds
        ):
            self._state = CircuitState.HALF_OPEN
            self._consecutive_successes = 0
            self._half_open_probe_in_flight = False

    def _seconds_until_retry(self) -> float:
        if self._opened_at is None:
            return 0.0
        remaining = self.cooldown_seconds - (time.monotonic() - self._opened_at)
        return max(0.0, remaining)

    # ------------------------------------------------------------------
    # Decorator interface
    # ------------------------------------------------------------------

    def __call__(self, func: Callable) -> Callable:
        """Allow the circuit breaker to be used as a function decorator."""
        import functools

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return self.call(func, *args, **kwargs)

        return wrapper

    def __repr__(self) -> str:
        return (
            f"CircuitBreaker(name={self.name!r}, state={self._state.value}, "
            f"failure_threshold={self.failure_threshold}, "
            f"cooldown_seconds={self.cooldown_seconds})"
        )
