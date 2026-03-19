"""Tests for the health_check helper module."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers.health_check import (
    HealthCheckRegistry,
    HealthCheckResult,
    HealthCheckStatus,
    async_check_http_endpoint,
    async_perform_health_check,
)


# ---------------------------------------------------------------------------
# HealthCheckStatus
# ---------------------------------------------------------------------------


def test_health_check_status_values() -> None:
    """HealthCheckStatus must expose the three canonical string values."""
    assert HealthCheckStatus.OK == "ok"
    assert HealthCheckStatus.DEGRADED == "degraded"
    assert HealthCheckStatus.UNAVAILABLE == "unavailable"


# ---------------------------------------------------------------------------
# HealthCheckResult
# ---------------------------------------------------------------------------


def test_health_check_result_as_dict_minimal() -> None:
    """as_dict returns at least the status key."""
    result = HealthCheckResult(status=HealthCheckStatus.OK)
    assert result.as_dict() == {"status": HealthCheckStatus.OK}


def test_health_check_result_as_dict_full() -> None:
    """as_dict includes all populated fields."""
    result = HealthCheckResult(
        status=HealthCheckStatus.DEGRADED,
        latency_ms=12.5,
        details={"http_status": 503},
        error="HTTP 503",
    )
    d = result.as_dict()
    assert d["status"] == HealthCheckStatus.DEGRADED
    assert d["latency_ms"] == 12.5
    assert d["http_status"] == 503
    assert d["error"] == "HTTP 503"


def test_health_check_result_as_dict_no_latency() -> None:
    """latency_ms is omitted when None."""
    result = HealthCheckResult(
        status=HealthCheckStatus.UNAVAILABLE,
        error="timeout",
    )
    d = result.as_dict()
    assert "latency_ms" not in d
    assert d["error"] == "timeout"


# ---------------------------------------------------------------------------
# HealthCheckRegistry
# ---------------------------------------------------------------------------


async def test_registry_register_and_domains(hass: HomeAssistant) -> None:
    """Registered domain appears in domains list."""
    registry = HealthCheckRegistry(hass)

    async def _check(h: HomeAssistant) -> dict[str, Any]:
        return {"status": HealthCheckStatus.OK}

    registry.async_register("test_domain", _check)
    assert "test_domain" in registry.domains


async def test_registry_run_checks_success(hass: HomeAssistant) -> None:
    """run_checks returns the callback result for each domain."""
    registry = HealthCheckRegistry(hass)

    async def _check(h: HomeAssistant) -> dict[str, Any]:
        return {"status": HealthCheckStatus.OK, "detail": "value"}

    registry.async_register("alpha", _check)
    results = await registry.async_run_checks()

    assert results["alpha"]["status"] == HealthCheckStatus.OK
    assert results["alpha"]["detail"] == "value"


async def test_registry_run_checks_partial_failure(hass: HomeAssistant) -> None:
    """A failing check does not prevent other checks from returning."""
    registry = HealthCheckRegistry(hass)

    async def _ok_check(h: HomeAssistant) -> dict[str, Any]:
        return {"status": HealthCheckStatus.OK}

    async def _bad_check(h: HomeAssistant) -> dict[str, Any]:
        raise RuntimeError("boom")

    registry.async_register("ok_domain", _ok_check)
    registry.async_register("bad_domain", _bad_check)

    results = await registry.async_run_checks()

    assert results["ok_domain"]["status"] == HealthCheckStatus.OK
    assert results["bad_domain"]["status"] == HealthCheckStatus.UNAVAILABLE
    assert "error" in results["bad_domain"]


async def test_registry_run_checks_empty(hass: HomeAssistant) -> None:
    """run_checks returns an empty dict when no checks are registered."""
    registry = HealthCheckRegistry(hass)
    assert await registry.async_run_checks() == {}


async def test_registry_run_single_check(hass: HomeAssistant) -> None:
    """run_check returns result for a specific domain."""
    registry = HealthCheckRegistry(hass)

    async def _check(h: HomeAssistant) -> dict[str, Any]:
        return {"status": HealthCheckStatus.OK}

    registry.async_register("my_domain", _check)
    result = await registry.async_run_check("my_domain")
    assert result is not None
    assert result["status"] == HealthCheckStatus.OK


async def test_registry_run_check_unknown_domain(hass: HomeAssistant) -> None:
    """run_check returns None for an unregistered domain."""
    registry = HealthCheckRegistry(hass)
    assert await registry.async_run_check("nonexistent") is None


# ---------------------------------------------------------------------------
# async_perform_health_check
# ---------------------------------------------------------------------------


async def test_perform_health_check_success() -> None:
    """Successful coroutine → OK status with latency."""

    async def _fast() -> None:
        await asyncio.sleep(0)

    result = await async_perform_health_check(_fast())
    assert result.status == HealthCheckStatus.OK
    assert result.latency_ms is not None
    assert result.latency_ms >= 0
    assert result.error is None


async def test_perform_health_check_timeout() -> None:
    """Coroutine that exceeds timeout → UNAVAILABLE with 'timeout' error."""

    async def _slow() -> None:
        await asyncio.sleep(100)

    result = await async_perform_health_check(_slow(), timeout=0.01)
    assert result.status == HealthCheckStatus.UNAVAILABLE
    assert result.error == "timeout"
    assert result.latency_ms is None


async def test_perform_health_check_exception() -> None:
    """Coroutine that raises → UNAVAILABLE with error message."""

    async def _broken() -> None:
        raise ValueError("something went wrong")

    result = await async_perform_health_check(_broken())
    assert result.status == HealthCheckStatus.UNAVAILABLE
    assert "something went wrong" in (result.error or "")


# ---------------------------------------------------------------------------
# async_check_http_endpoint
# ---------------------------------------------------------------------------


async def test_check_http_endpoint_ok(
    hass: HomeAssistant,
    aioclient_mock: Any,
) -> None:
    """HTTP 200 response → OK status with latency and http_status detail."""
    aioclient_mock.get("http://example.com/health", status=200, text="ok")

    result = await async_check_http_endpoint(hass, "http://example.com/health")

    assert result.status == HealthCheckStatus.OK
    assert result.latency_ms is not None
    assert result.latency_ms >= 0
    assert result.details.get("http_status") == 200
    assert result.error is None


async def test_check_http_endpoint_server_error(
    hass: HomeAssistant,
    aioclient_mock: Any,
) -> None:
    """HTTP 500 response → DEGRADED status."""
    aioclient_mock.get("http://example.com/health", status=500, text="err")

    result = await async_check_http_endpoint(hass, "http://example.com/health")

    assert result.status == HealthCheckStatus.DEGRADED
    assert result.details.get("http_status") == 500
    assert result.error is not None


async def test_check_http_endpoint_connection_error(
    hass: HomeAssistant,
    aioclient_mock: Any,
) -> None:
    """Connection error → UNAVAILABLE status."""
    import aiohttp

    aioclient_mock.get("http://example.com/health", exc=aiohttp.ClientError)

    result = await async_check_http_endpoint(hass, "http://example.com/health")

    assert result.status == HealthCheckStatus.UNAVAILABLE
    assert result.error is not None


async def test_check_http_endpoint_timeout(
    hass: HomeAssistant,
    aioclient_mock: Any,
) -> None:
    """Timeout → UNAVAILABLE status with 'timeout' error."""
    aioclient_mock.get("http://example.com/health", exc=asyncio.TimeoutError)

    result = await async_check_http_endpoint(
        hass, "http://example.com/health", timeout=0.01
    )

    assert result.status == HealthCheckStatus.UNAVAILABLE
    assert result.error == "timeout"
