"""Provide info to system health for the HTTP integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components import system_health
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import health_check


@callback
def async_register(
    hass: HomeAssistant, register: system_health.SystemHealthRegistration
) -> None:
    """Register system health callbacks."""
    register.async_register_info(system_health_info)


async def system_health_info(hass: HomeAssistant) -> dict[str, Any]:
    """Get info for the system health page.

    Opens an actual TCP connection to the local HTTP server to verify it
    is accepting connections and measures the connection setup latency.
    This provides a real liveness check rather than a static "ok".
    """
    server = hass.http
    server_port: int = server.server_port
    use_ssl: bool = server.ssl_certificate is not None

    result = await health_check.async_check_tcp_connection(
        "127.0.0.1", server_port
    )

    return {
        "server_port": server_port,
        "ssl_active": use_ssl,
        "server_reachable": result.as_system_health_dict(),
    }
