"""Health check for the ping integration."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.health_check import HealthCheckRegistry, HealthCheckStatus

from .const import DOMAIN


@callback
def async_register(hass: HomeAssistant, registry: HealthCheckRegistry) -> None:
    """Register ping health checks."""
    registry.async_register("ping", _async_health_check)


async def _async_health_check(hass: HomeAssistant) -> dict[str, Any]:
    """Aggregate ping results for all configured hosts.

    Iterates over every active ping config entry and reads the most-recent
    coordinator data.  Latency figures come directly from the ICMP
    measurement, so no new network calls are made.

    Status rules:
    - **OK** – every host is reachable.
    - **DEGRADED** – at least one host is reachable but not all.
    - **UNAVAILABLE** – no host is reachable, or no hosts are configured.
    """
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        return {
            "status": HealthCheckStatus.UNAVAILABLE,
            "error": "No ping hosts configured",
        }

    hosts: list[dict[str, Any]] = []
    all_alive = True
    any_alive = False

    for entry in entries:
        coordinator = getattr(entry, "runtime_data", None)
        if coordinator is None or coordinator.data is None:
            hosts.append(
                {
                    "host": entry.title,
                    "alive": False,
                    "error": "No data available",
                }
            )
            all_alive = False
            continue

        data = coordinator.data
        host_info: dict[str, Any] = {
            "host": data.ip_address,
            "alive": data.is_alive,
        }

        # Attach round-trip latency when available.
        if data.is_alive and data.data:
            avg_rtt = data.data.get("avg")
            if avg_rtt is not None:
                host_info["latency_ms"] = avg_rtt

        if data.is_alive:
            any_alive = True
        else:
            all_alive = False

        hosts.append(host_info)

    if all_alive:
        status = HealthCheckStatus.OK
    elif any_alive:
        status = HealthCheckStatus.DEGRADED
    else:
        status = HealthCheckStatus.UNAVAILABLE

    return {
        "status": status,
        "hosts": hosts,
    }
