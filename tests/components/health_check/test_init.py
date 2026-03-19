"""Tests for the health_check component."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.health_check.const import DATA_HEALTH_CHECK, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.health_check import HealthCheckRegistry, HealthCheckStatus
from homeassistant.setup import async_setup_component

from tests.common import mock_platform
from tests.typing import WebSocketGenerator


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


async def _setup(hass: HomeAssistant) -> None:
    """Set up the health_check component."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------


async def test_async_setup_creates_registry(hass: HomeAssistant) -> None:
    """async_setup stores a HealthCheckRegistry in hass.data."""
    await _setup(hass)
    assert DATA_HEALTH_CHECK in hass.data
    assert isinstance(hass.data[DATA_HEALTH_CHECK], HealthCheckRegistry)


# ---------------------------------------------------------------------------
# WebSocket API
# ---------------------------------------------------------------------------


async def test_websocket_no_checks_registered(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """health_check/info returns results when only automatically-loaded platforms exist."""
    await _setup(hass)
    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "health_check/info"})
    msg = await client.receive_json()

    assert msg["success"] is True
    # The registry may contain auto-loaded platforms (e.g. http); the response
    # must be a dict regardless of whether it is empty or not.
    assert isinstance(msg["result"], dict)


async def test_websocket_returns_check_results(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """health_check/info returns aggregated results from all registered checks."""
    await _setup(hass)

    registry: HealthCheckRegistry = hass.data[DATA_HEALTH_CHECK]
    registry.async_register(
        "my_service",
        AsyncMock(
            return_value={
                "status": HealthCheckStatus.OK,
                "latency_ms": 5.0,
            }
        ),
    )

    client = await hass_ws_client(hass)
    await client.send_json({"id": 2, "type": "health_check/info"})
    msg = await client.receive_json()

    assert msg["success"] is True
    result = msg["result"]
    assert "my_service" in result
    assert result["my_service"]["status"] == HealthCheckStatus.OK
    assert result["my_service"]["latency_ms"] == 5.0


async def test_websocket_partial_failure(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """A failing check does not prevent other results from being returned."""
    await _setup(hass)

    registry: HealthCheckRegistry = hass.data[DATA_HEALTH_CHECK]

    registry.async_register(
        "good_service",
        AsyncMock(return_value={"status": HealthCheckStatus.OK}),
    )

    async def _raise(h: HomeAssistant) -> dict[str, Any]:
        raise RuntimeError("boom")

    registry.async_register("bad_service", _raise)

    client = await hass_ws_client(hass)
    await client.send_json({"id": 3, "type": "health_check/info"})
    msg = await client.receive_json()

    assert msg["success"] is True
    result = msg["result"]
    assert result["good_service"]["status"] == HealthCheckStatus.OK
    assert result["bad_service"]["status"] == HealthCheckStatus.UNAVAILABLE


# ---------------------------------------------------------------------------
# Platform loading
# ---------------------------------------------------------------------------


async def test_platform_loading(hass: HomeAssistant) -> None:
    """health_check platforms are discovered and their async_register called."""
    hass.config.components.add("fake_integration")
    called_with: list[tuple] = []

    def _register(h: HomeAssistant, registry: HealthCheckRegistry) -> None:
        called_with.append((h, registry))

    mock_platform(
        hass,
        "fake_integration.health_check",
        Mock(async_register=_register),
    )

    await _setup(hass)

    # async_register should have been called once with the registry
    assert len(called_with) == 1
    assert called_with[0][0] is hass
    assert isinstance(called_with[0][1], HealthCheckRegistry)


async def test_platform_loading_missing_async_register(hass: HomeAssistant) -> None:
    """A platform without async_register is silently skipped."""
    hass.config.components.add("bad_integration")

    # Platform with no async_register attribute
    mock_platform(
        hass,
        "bad_integration.health_check",
        Mock(spec=[]),  # no async_register
    )

    # Should not raise
    await _setup(hass)
