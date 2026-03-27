"""Health check utilities for Home Assistant integrations.

This module provides shared utilities to validate real service availability,
measure response latency, and handle partial failures across integrations.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
import logging
import time
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

DEFAULT_ENDPOINT_TIMEOUT = 5.0
DEFAULT_TCP_TIMEOUT = 5.0


@dataclass(slots=True, frozen=True)
class HealthCheckResult:
    """Result of a health check operation.

    Attributes:
        ok: Whether the health check succeeded.
        latency_ms: Round-trip latency in milliseconds, or None on failure.
        error: Short error description when ok is False.
        timestamp: UTC datetime when the health check was performed.

    """

    ok: bool
    latency_ms: float | None
    error: str | None
    timestamp: datetime

    def as_system_health_dict(self) -> dict[str, Any] | str:
        """Convert to a value suitable for use in system health info dicts.

        Returns "ok" on success (or "Xms" when latency is available),
        and a ``{"type": "failed", "error": "..."}`` dict on failure.
        """
        if self.ok:
            if self.latency_ms is not None:
                return f"{self.latency_ms:.0f}ms"
            return "ok"
        return {"type": "failed", "error": self.error or "unknown"}


async def async_check_endpoint(
    hass: HomeAssistant,
    url: str,
    timeout: float = DEFAULT_ENDPOINT_TIMEOUT,
) -> HealthCheckResult:
    """Check whether an HTTP endpoint is reachable and measure response latency.

    Any HTTP response status is treated as reachable (the endpoint is up).
    Only network-level errors (connection refused, DNS failure, timeout) are
    treated as failures.

    Args:
        hass: The Home Assistant instance.
        url: The HTTP(S) URL to check.
        timeout: Maximum seconds to wait for a response.

    Returns:
        A :class:`HealthCheckResult` with real latency data.

    """
    session = aiohttp_client.async_get_clientsession(hass)
    start = time.monotonic()
    timestamp = dt_util.utcnow()

    try:
        async with asyncio.timeout(timeout):
            async with session.get(url) as _response:
                latency_ms = (time.monotonic() - start) * 1000
                _LOGGER.debug(
                    "Health check for %s succeeded in %.0f ms", url, latency_ms
                )
                return HealthCheckResult(
                    ok=True,
                    latency_ms=latency_ms,
                    error=None,
                    timestamp=timestamp,
                )
    except TimeoutError:
        _LOGGER.debug("Health check for %s timed out after %.1f s", url, timeout)
        return HealthCheckResult(
            ok=False,
            latency_ms=None,
            error="timeout",
            timestamp=timestamp,
        )
    except aiohttp.ClientError as err:
        _LOGGER.debug("Health check for %s failed: %s", url, err)
        return HealthCheckResult(
            ok=False,
            latency_ms=None,
            error="unreachable",
            timestamp=timestamp,
        )


async def async_check_tcp_connection(
    host: str,
    port: int,
    timeout: float = DEFAULT_TCP_TIMEOUT,
) -> HealthCheckResult:
    """Check whether a TCP host:port is connectable and measure connection latency.

    Args:
        host: Hostname or IP address to connect to.
        port: TCP port number.
        timeout: Maximum seconds to wait for a connection.

    Returns:
        A :class:`HealthCheckResult` with real connection latency.

    """
    start = time.monotonic()
    timestamp = dt_util.utcnow()

    try:
        async with asyncio.timeout(timeout):
            _reader, writer = await asyncio.open_connection(host, port)
            latency_ms = (time.monotonic() - start) * 1000
            writer.close()
            await writer.wait_closed()
            _LOGGER.debug(
                "TCP health check for %s:%d succeeded in %.0f ms",
                host,
                port,
                latency_ms,
            )
            return HealthCheckResult(
                ok=True,
                latency_ms=latency_ms,
                error=None,
                timestamp=timestamp,
            )
    except TimeoutError:
        _LOGGER.debug(
            "TCP health check for %s:%d timed out after %.1f s", host, port, timeout
        )
        return HealthCheckResult(
            ok=False,
            latency_ms=None,
            error="timeout",
            timestamp=timestamp,
        )
    except OSError as err:
        _LOGGER.debug("TCP health check for %s:%d failed: %s", host, port, err)
        return HealthCheckResult(
            ok=False,
            latency_ms=None,
            error="unreachable",
            timestamp=timestamp,
        )
