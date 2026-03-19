"""Health Check integration for monitoring service availability."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    config_validation as cv,
    integration_platform,
)
from homeassistant.helpers.health_check import HealthCheckRegistry
from homeassistant.helpers.typing import ConfigType

from .const import DATA_HEALTH_CHECK, DOMAIN

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the health check component."""
    registry = HealthCheckRegistry(hass)
    hass.data[DATA_HEALTH_CHECK] = registry

    websocket_api.async_register_command(hass, websocket_health_check_info)

    await integration_platform.async_process_integration_platforms(
        hass, DOMAIN, _process_health_check_platform
    )

    return True


@callback
def _process_health_check_platform(
    hass: HomeAssistant,
    integration_domain: str,
    platform: Any,
) -> None:
    """Register a health check platform discovered from an integration."""
    if not hasattr(platform, "async_register"):
        return
    registry: HealthCheckRegistry | None = hass.data.get(DATA_HEALTH_CHECK)
    if registry is None:
        return
    try:
        platform.async_register(hass, registry)
    except Exception:  # noqa: BLE001
        _LOGGER.exception(
            "Error registering health check for %s", integration_domain
        )


@websocket_api.websocket_command({"type": "health_check/info"})
@websocket_api.async_response
async def websocket_health_check_info(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle the health_check/info websocket command.

    Runs all registered health checks concurrently and returns the
    aggregated results in a single response message. Individual check
    failures are captured per-domain so partial results are always
    returned to the caller.
    """
    registry: HealthCheckRegistry | None = hass.data.get(DATA_HEALTH_CHECK)
    if registry is None:
        connection.send_result(msg["id"], {})
        return

    results = await registry.async_run_checks()
    connection.send_result(msg["id"], results)
