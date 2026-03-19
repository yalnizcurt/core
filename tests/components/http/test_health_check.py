"""Tests for the HTTP health check."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers.health_check import HealthCheckStatus

from homeassistant.components.http.health_check import _async_health_check


async def test_http_health_check_server_running_no_ssl(hass: HomeAssistant) -> None:
    """When the HTTP server is running without SSL the status is OK."""
    mock_http = MagicMock()
    mock_http.site = MagicMock()  # truthy → server is running
    mock_http.context = None  # no SSL

    hass.http = mock_http  # type: ignore[attr-defined]

    result = await _async_health_check(hass)

    assert result["status"] == HealthCheckStatus.OK
    assert result["server_running"] is True
    assert result["ssl_enabled"] is False


async def test_http_health_check_server_running_with_ssl(hass: HomeAssistant) -> None:
    """When SSL is configured, ssl_enabled is True."""
    mock_http = MagicMock()
    mock_http.site = MagicMock()
    mock_http.context = MagicMock()  # truthy → SSL is active

    hass.http = mock_http  # type: ignore[attr-defined]

    result = await _async_health_check(hass)

    assert result["status"] == HealthCheckStatus.OK
    assert result["ssl_enabled"] is True


async def test_http_health_check_server_not_running(hass: HomeAssistant) -> None:
    """When the server site is None the status is UNAVAILABLE."""
    mock_http = MagicMock()
    mock_http.site = None  # server not yet started
    mock_http.context = None

    hass.http = mock_http  # type: ignore[attr-defined]

    result = await _async_health_check(hass)

    assert result["status"] == HealthCheckStatus.UNAVAILABLE
    assert result["server_running"] is False
    assert "error" in result


async def test_http_health_check_not_initialised(hass: HomeAssistant) -> None:
    """When hass.http is None (not yet set up) the status is UNAVAILABLE."""
    # In a bare test hass, hass.http is None (the class-level default).
    # The health check function uses getattr(..., None) so it is safe.
    assert hass.http is None  # sanity check – HTTP not set up in this test
    result = await _async_health_check(hass)

    assert result["status"] == HealthCheckStatus.UNAVAILABLE
    assert "error" in result
