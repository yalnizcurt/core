"""Health check utilities for Home Assistant integrations."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from enum import StrEnum
import logging
import time
from typing import Any

from homeassistant.core import HomeAssistant, callback

_LOGGER = logging.getLogger(__name__)

HEALTH_CHECK_TIMEOUT = 10.0

type HealthCheckCallbackType = Callable[
    [HomeAssistant], Coroutine[Any, Any, dict[str, Any]]
]


class HealthCheckStatus(StrEnum):
    """Health check status values."""

    OK = "ok"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


@dataclass
class HealthCheckResult:
    """Result of a single health check."""

    status: HealthCheckStatus
    latency_ms: float | None = None
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return the result as a serializable dict."""
        result: dict[str, Any] = {"status": self.status}
        if self.latency_ms is not None:
            result["latency_ms"] = self.latency_ms
        if self.details:
            result.update(self.details)
        if self.error is not None:
            result["error"] = self.error
        return result


@dataclass
class HealthCheckRegistration:
    """Tracks a health check registration for one domain."""

    domain: str
    check_fn: HealthCheckCallbackType
    manage_url: str | None = None


class HealthCheckRegistry:
    """Registry that aggregates health checks across integrations."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the registry."""
        self.hass = hass
        self._registrations: dict[str, HealthCheckRegistration] = {}

    @callback
    def async_register(
        self,
        domain: str,
        check_fn: HealthCheckCallbackType,
        manage_url: str | None = None,
    ) -> None:
        """Register a health check callback for *domain*."""
        self._registrations[domain] = HealthCheckRegistration(
            domain=domain,
            check_fn=check_fn,
            manage_url=manage_url,
        )

    async def async_run_checks(self) -> dict[str, dict[str, Any]]:
        """Run all registered checks concurrently and handle partial failures.

        A failure in one check does not prevent other checks from running.
        """
        if not self._registrations:
            return {}

        tasks = {
            domain: asyncio.create_task(
                _async_run_single_check(self.hass, registration),
                name=f"health_check_{domain}",
            )
            for domain, registration in self._registrations.items()
        }

        gathered = await asyncio.gather(*tasks.values(), return_exceptions=True)
        results: dict[str, dict[str, Any]] = {}
        for domain, result in zip(tasks, gathered):
            if isinstance(result, BaseException):
                results[domain] = {
                    "status": HealthCheckStatus.UNAVAILABLE,
                    "error": str(result),
                }
            else:
                results[domain] = result
        return results

    async def async_run_check(self, domain: str) -> dict[str, Any] | None:
        """Run the health check for a single domain."""
        registration = self._registrations.get(domain)
        if not registration:
            return None
        return await _async_run_single_check(self.hass, registration)

    @property
    def domains(self) -> list[str]:
        """Return a list of all registered domain names."""
        return list(self._registrations)


async def _async_run_single_check(
    hass: HomeAssistant,
    registration: HealthCheckRegistration,
) -> dict[str, Any]:
    """Execute one health check callback, catching any exception."""
    try:
        return await registration.check_fn(hass)
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Error running health check for %s", registration.domain)
        return {
            "status": HealthCheckStatus.UNAVAILABLE,
            "error": "unexpected error",
        }


async def async_perform_health_check(
    coro: Coroutine[Any, Any, Any],
    timeout: float = HEALTH_CHECK_TIMEOUT,
) -> HealthCheckResult:
    """Run *coro* and measure its wall-clock latency.

    Returns a :class:`HealthCheckResult` with:
    - ``status``: OK on success, UNAVAILABLE on timeout or exception.
    - ``latency_ms``: round-trip time in milliseconds (None on failure).
    - ``error``: human-readable error string on failure.
    """
    start = time.monotonic()
    try:
        async with asyncio.timeout(timeout):
            await coro
        latency_ms = round((time.monotonic() - start) * 1000, 2)
        return HealthCheckResult(
            status=HealthCheckStatus.OK,
            latency_ms=latency_ms,
        )
    except asyncio.TimeoutError:
        return HealthCheckResult(
            status=HealthCheckStatus.UNAVAILABLE,
            error="timeout",
        )
    except Exception as err:  # noqa: BLE001
        return HealthCheckResult(
            status=HealthCheckStatus.UNAVAILABLE,
            error=str(err),
        )


async def async_check_http_endpoint(
    hass: HomeAssistant,
    url: str,
    timeout: float = HEALTH_CHECK_TIMEOUT,
) -> HealthCheckResult:
    """Perform an HTTP GET to *url* and return a latency-measured result.

    - HTTP < 500  → :attr:`HealthCheckStatus.OK`
    - HTTP >= 500 → :attr:`HealthCheckStatus.DEGRADED`
    - Connection error / timeout → :attr:`HealthCheckStatus.UNAVAILABLE`
    """
    from homeassistant.helpers.aiohttp_client import (  # noqa: PLC0415
        async_get_clientsession,
    )

    session = async_get_clientsession(hass)
    start = time.monotonic()
    try:
        async with asyncio.timeout(timeout):
            async with session.get(url) as response:
                latency_ms = round((time.monotonic() - start) * 1000, 2)
                if response.status < 500:
                    return HealthCheckResult(
                        status=HealthCheckStatus.OK,
                        latency_ms=latency_ms,
                        details={"http_status": response.status},
                    )
                return HealthCheckResult(
                    status=HealthCheckStatus.DEGRADED,
                    latency_ms=latency_ms,
                    details={"http_status": response.status},
                    error=f"HTTP {response.status}",
                )
    except asyncio.TimeoutError:
        return HealthCheckResult(
            status=HealthCheckStatus.UNAVAILABLE,
            error="timeout",
        )
    except Exception as err:  # noqa: BLE001
        return HealthCheckResult(
            status=HealthCheckStatus.UNAVAILABLE,
            error=str(err),
        )
