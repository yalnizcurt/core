"""Provide info to system health for the Ping (ICMP) integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components import system_health
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .coordinator import PingConfigEntry


@callback
def async_register(
    hass: HomeAssistant, register: system_health.SystemHealthRegistration
) -> None:
    """Register system health callbacks."""
    register.async_register_info(system_health_info)


async def system_health_info(hass: HomeAssistant) -> dict[str, Any]:
    """Get info for the system health page.

    Reports the current reachability status and average round-trip latency
    for each configured ping target.  The data comes from the most recent
    coordinator update, so it reflects real measured values rather than a
    static "ok".
    """
    all_entries: list[PingConfigEntry] = hass.config_entries.async_entries(DOMAIN)
    entries = [e for e in all_entries if e.state is ConfigEntryState.LOADED]
    info: dict[str, Any] = {"monitored_hosts": len(entries)}

    reachable = 0
    unreachable = 0

    for entry in entries:
        coordinator = entry.runtime_data
        result = coordinator.data
        host: str = (
            result.ip_address
            if result is not None
            else entry.options.get(CONF_HOST, entry.title)
        )

        if result is None or not coordinator.last_update_success:
            unreachable += 1
            info[f"{host}_reachable"] = {"type": "failed", "error": "unreachable"}
            continue

        if result.is_alive:
            reachable += 1
            info[f"{host}_reachable"] = "ok"
            if result.data:
                avg_rtt = result.data.get("avg")
                if avg_rtt is not None:
                    info[f"{host}_latency_ms"] = round(float(avg_rtt), 1)
        else:
            unreachable += 1
            info[f"{host}_reachable"] = {"type": "failed", "error": "unreachable"}

    info["reachable_hosts"] = reachable
    info["unreachable_hosts"] = unreachable

    return info
