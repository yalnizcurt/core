"""Health check for the HTTP integration."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.health_check import HealthCheckRegistry, HealthCheckStatus


@callback
def async_register(hass: HomeAssistant, registry: HealthCheckRegistry) -> None:
    """Register HTTP health checks."""
    registry.async_register("http", _async_health_check)


async def _async_health_check(hass: HomeAssistant) -> dict[str, Any]:
    """Check HTTP server availability.

    Reports whether the embedded HTTP server is initialized and actively
    listening, and whether TLS/SSL is enabled.  No outbound network
    connections are made; the check reads internal server state only.
    """
    http = getattr(hass, "http", None)
    if http is None:
        return {
            "status": HealthCheckStatus.UNAVAILABLE,
            "error": "HTTP server not initialized",
        }

    server_running = http.site is not None
    ssl_enabled = http.context is not None

    if server_running:
        return {
            "status": HealthCheckStatus.OK,
            "server_running": server_running,
            "ssl_enabled": ssl_enabled,
        }

    return {
        "status": HealthCheckStatus.UNAVAILABLE,
        "server_running": server_running,
        "ssl_enabled": ssl_enabled,
        "error": "HTTP server not running",
    }
