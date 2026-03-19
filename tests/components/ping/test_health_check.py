"""Tests for the ping health check."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers.health_check import HealthCheckStatus

from homeassistant.components.ping.health_check import _async_health_check


def _make_entry(
    title: str,
    ip_address: str,
    is_alive: bool,
    avg_rtt: float | None = None,
) -> MagicMock:
    """Build a mock config entry whose runtime_data mimics PingUpdateCoordinator."""
    coordinator_data = MagicMock()
    coordinator_data.ip_address = ip_address
    coordinator_data.is_alive = is_alive
    coordinator_data.data = {"avg": avg_rtt} if avg_rtt is not None else {}

    coordinator = MagicMock()
    coordinator.data = coordinator_data

    entry = MagicMock()
    entry.title = title
    entry.runtime_data = coordinator
    return entry


async def test_ping_health_check_all_alive(hass: HomeAssistant) -> None:
    """All hosts alive → OK status with latency in host info."""
    entry = _make_entry("router", "192.168.1.1", is_alive=True, avg_rtt=3.2)

    with MagicMock() as mock_entries:
        hass.config_entries.async_entries = MagicMock(return_value=[entry])
        result = await _async_health_check(hass)

    assert result["status"] == HealthCheckStatus.OK
    assert len(result["hosts"]) == 1
    host = result["hosts"][0]
    assert host["alive"] is True
    assert host["latency_ms"] == 3.2


async def test_ping_health_check_all_unreachable(hass: HomeAssistant) -> None:
    """All hosts unreachable → UNAVAILABLE."""
    entry = _make_entry("router", "192.168.1.1", is_alive=False)
    hass.config_entries.async_entries = MagicMock(return_value=[entry])

    result = await _async_health_check(hass)

    assert result["status"] == HealthCheckStatus.UNAVAILABLE
    assert result["hosts"][0]["alive"] is False


async def test_ping_health_check_partial_failure(hass: HomeAssistant) -> None:
    """Some hosts alive, some not → DEGRADED."""
    entry_ok = _make_entry("host1", "10.0.0.1", is_alive=True, avg_rtt=1.0)
    entry_bad = _make_entry("host2", "10.0.0.2", is_alive=False)
    hass.config_entries.async_entries = MagicMock(return_value=[entry_ok, entry_bad])

    result = await _async_health_check(hass)

    assert result["status"] == HealthCheckStatus.DEGRADED
    assert len(result["hosts"]) == 2


async def test_ping_health_check_no_entries(hass: HomeAssistant) -> None:
    """No ping entries configured → UNAVAILABLE."""
    hass.config_entries.async_entries = MagicMock(return_value=[])

    result = await _async_health_check(hass)

    assert result["status"] == HealthCheckStatus.UNAVAILABLE
    assert "error" in result


async def test_ping_health_check_no_coordinator_data(hass: HomeAssistant) -> None:
    """Entry with no coordinator data → treated as dead host, UNAVAILABLE."""
    entry = MagicMock()
    entry.title = "ghost"
    entry.runtime_data = None  # coordinator not yet initialized

    hass.config_entries.async_entries = MagicMock(return_value=[entry])

    result = await _async_health_check(hass)

    assert result["status"] == HealthCheckStatus.UNAVAILABLE
    assert result["hosts"][0]["alive"] is False
    assert "error" in result["hosts"][0]
