"""Tests for the MQTT health check."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers.health_check import HealthCheckStatus

from homeassistant.components.mqtt.health_check import _async_health_check


async def test_mqtt_health_check_connected(hass: HomeAssistant) -> None:
    """When the MQTT client is connected the status is OK."""
    from homeassistant.components.mqtt.models import DATA_MQTT

    mock_client = MagicMock()
    mock_client.connected = True

    mock_mqtt_data = MagicMock()
    mock_mqtt_data.client = mock_client

    hass.data[DATA_MQTT] = mock_mqtt_data

    result = await _async_health_check(hass)

    assert result["status"] == HealthCheckStatus.OK
    assert result["connected"] is True
    assert "error" not in result


async def test_mqtt_health_check_disconnected(hass: HomeAssistant) -> None:
    """When the MQTT client is disconnected the status is UNAVAILABLE."""
    from homeassistant.components.mqtt.models import DATA_MQTT

    mock_client = MagicMock()
    mock_client.connected = False

    mock_mqtt_data = MagicMock()
    mock_mqtt_data.client = mock_client

    hass.data[DATA_MQTT] = mock_mqtt_data

    result = await _async_health_check(hass)

    assert result["status"] == HealthCheckStatus.UNAVAILABLE
    assert result["connected"] is False
    assert "error" in result


async def test_mqtt_health_check_not_initialized(hass: HomeAssistant) -> None:
    """When MQTT is not set up the status is UNAVAILABLE."""
    # Do NOT put anything in hass.data[DATA_MQTT]
    result = await _async_health_check(hass)

    assert result["status"] == HealthCheckStatus.UNAVAILABLE
    assert "error" in result
    assert "not initialized" in result["error"].lower()
