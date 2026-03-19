"""Health check for the MQTT integration."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.health_check import HealthCheckRegistry, HealthCheckStatus


@callback
def async_register(hass: HomeAssistant, registry: HealthCheckRegistry) -> None:
    """Register MQTT health checks."""
    registry.async_register("mqtt", _async_health_check)


async def _async_health_check(hass: HomeAssistant) -> dict[str, Any]:
    """Check MQTT broker connectivity.

    Reports whether the MQTT client is currently connected to the broker.
    Accessing the connection state is a pure in-memory read – no network
    activity is triggered.
    """
    from homeassistant.components.mqtt.models import (  # noqa: PLC0415
        DATA_MQTT,
    )

    mqtt_data = hass.data.get(DATA_MQTT)
    if mqtt_data is None:
        return {
            "status": HealthCheckStatus.UNAVAILABLE,
            "error": "MQTT not initialized",
        }

    connected: bool = mqtt_data.client.connected
    result: dict[str, Any] = {
        "status": HealthCheckStatus.OK if connected else HealthCheckStatus.UNAVAILABLE,
        "connected": connected,
    }

    if not connected:
        result["error"] = "Not connected to MQTT broker"

    return result
