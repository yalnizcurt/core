"""Provide info to system health for the RESTful integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components import system_health
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import health_check

from .const import COORDINATOR, DOMAIN, REST, REST_DATA

if TYPE_CHECKING:
    from .data import RestData


@callback
def async_register(
    hass: HomeAssistant, register: system_health.SystemHealthRegistration
) -> None:
    """Register system health callbacks."""
    register.async_register_info(system_health_info)


async def system_health_info(hass: HomeAssistant) -> dict[str, Any]:
    """Get info for the system health page.

    Performs a real-time HTTP request to each configured REST resource URL
    to measure actual endpoint reachability and response latency.  Partial
    failures (some endpoints up, some down) are reported individually.
    """
    domain_data: dict[str, list[Any]] = hass.data.get(DOMAIN, {})
    rest_entries: list[dict[str, Any]] = domain_data.get(REST_DATA, [])

    info: dict[str, Any] = {"configured_resources": len(rest_entries)}

    reachable = 0
    unreachable = 0

    for idx, entry in enumerate(rest_entries):
        rest: RestData = entry[REST]
        coordinator = entry[COORDINATOR]
        url: str = rest.url
        label = f"resource_{idx}"

        # Report coordinator's last known success status alongside real-time check.
        if not coordinator.last_update_success:
            info[f"{label}_last_update"] = {"type": "failed", "error": "update_failed"}
        else:
            info[f"{label}_last_update"] = "ok"

        # Perform a real-time reachability + latency check.
        result = await health_check.async_check_endpoint(hass, url)
        health_value = result.as_system_health_dict()

        if result.ok:
            reachable += 1
            info[f"{label}_endpoint"] = health_value
        else:
            unreachable += 1
            info[f"{label}_endpoint"] = health_value

    info["reachable_resources"] = reachable
    info["unreachable_resources"] = unreachable

    return info
