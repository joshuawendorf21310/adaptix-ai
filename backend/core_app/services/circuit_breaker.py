"""Circuit breaker for Bedrock resilience."""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit breaker pattern implementation for AI provider resilience.

    Prevents cascading failures by failing fast when provider is degraded.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        half_open_max_calls: int = 3,
    ) -> None:
        """
        Initialize circuit breaker.

        Args:
            name: Circuit breaker name
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery
            half_open_max_calls: Max calls allowed in half-open state
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: datetime | None = None
        self._half_open_calls = 0
        self._lock = asyncio.Lock()

    async def _current_state(self) -> CircuitState:
        """Get current circuit state with automatic transitions."""
        async with self._lock:
            if self._state == CircuitState.OPEN:
                # Check if recovery timeout has elapsed
                if self._last_failure_time:
                    elapsed = (datetime.now(UTC) - self._last_failure_time).total_seconds()
                    if elapsed >= self.recovery_timeout:
                        logger.info(f"Circuit breaker '{self.name}' transitioning to HALF_OPEN")
                        self._state = CircuitState.HALF_OPEN
                        self._half_open_calls = 0

            return self._state

    async def _record_success(self) -> None:
        """Record successful call."""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._half_open_calls += 1
                if self._half_open_calls >= self.half_open_max_calls:
                    logger.info(f"Circuit breaker '{self.name}' CLOSED after recovery")
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._half_open_calls = 0
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0  # Reset failure count on success

    async def _record_failure(self, error: Exception) -> None:
        """Record failed call."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.now(UTC)

            if self._state == CircuitState.HALF_OPEN:
                logger.warning(f"Circuit breaker '{self.name}' OPEN after half-open failure")
                self._state = CircuitState.OPEN
                self._half_open_calls = 0
            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self.failure_threshold:
                    logger.warning(
                        f"Circuit breaker '{self.name}' OPEN after {self._failure_count} failures"
                    )
                    self._state = CircuitState.OPEN

    async def get_status(self) -> dict[str, Any]:
        """Get circuit breaker status."""
        state = await self._current_state()
        return {
            "name": self.name,
            "state": state.value,
            "failure_count": self._failure_count,
            "last_failure_time": self._last_failure_time.isoformat() if self._last_failure_time else None,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
        }

    async def reset(self) -> None:
        """Manually reset circuit breaker."""
        async with self._lock:
            logger.info(f"Circuit breaker '{self.name}' manually RESET")
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._half_open_calls = 0
            self._last_failure_time = None


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers."""

    _breakers: dict[str, CircuitBreaker] = {}

    @classmethod
    def get(
        cls,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        half_open_max_calls: int = 3,
    ) -> CircuitBreaker:
        """Get or create a circuit breaker."""
        if name not in cls._breakers:
            cls._breakers[name] = CircuitBreaker(
                name=name,
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
                half_open_max_calls=half_open_max_calls,
            )
        return cls._breakers[name]

    @classmethod
    async def get_all_status(cls) -> list[dict[str, Any]]:
        """Get status of all registered circuit breakers."""
        statuses = []
        for breaker in cls._breakers.values():
            status = await breaker.get_status()
            statuses.append(status)
        return statuses

    @classmethod
    async def reset_all(cls) -> None:
        """Reset all circuit breakers."""
        for breaker in cls._breakers.values():
            await breaker.reset()
