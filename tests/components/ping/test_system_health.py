"""Tests for the Ping integration system health."""

from __future__ import annotations

import pytest

from homeassistant.components.ping.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, get_system_health_info


@pytest.mark.usefixtures("setup_integration")
async def test_ping_system_health_host_reachable(
    hass: HomeAssistant,
) -> None:
    """Test system health info when the ping target is reachable."""
    assert await async_setup_component(hass, "system_health", {})
    await hass.async_block_till_done()

    info = await get_system_health_info(hass, DOMAIN)

    assert info["monitored_hosts"] == 1
    assert info["reachable_hosts"] == 1
    assert info["unreachable_hosts"] == 0
    assert info["10.10.10.10_reachable"] == "ok"
    # Average RTT comes from the mock Host(…, [10, 1, 2, 5, 6]) fixture.
    assert "10.10.10.10_latency_ms" in info


@pytest.mark.usefixtures("setup_integration")
async def test_ping_system_health_no_data(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test system health reports unreachable when coordinator has no data."""
    # Wipe coordinator data to simulate a failed first update.
    coordinator = config_entry.runtime_data
    coordinator.data = None
    coordinator.last_update_success = False

    assert await async_setup_component(hass, "system_health", {})
    await hass.async_block_till_done()

    info = await get_system_health_info(hass, DOMAIN)

    assert info["unreachable_hosts"] == 1
    assert info["reachable_hosts"] == 0
    # Key is derived from entry title when result is None.
    host_key = f"{config_entry.title}_reachable"
    assert info[host_key] == {"type": "failed", "error": "unreachable"}


@pytest.mark.usefixtures("setup_integration")
async def test_ping_system_health_host_unreachable(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test system health reports unreachable when host is not alive."""
    from homeassistant.components.ping.coordinator import PingResult

    coordinator = config_entry.runtime_data
    coordinator.data = PingResult(
        ip_address="10.10.10.10",
        is_alive=False,
        data=None,
    )

    assert await async_setup_component(hass, "system_health", {})
    await hass.async_block_till_done()

    info = await get_system_health_info(hass, DOMAIN)

    assert info["unreachable_hosts"] == 1
    assert info["reachable_hosts"] == 0
    assert info["10.10.10.10_reachable"] == {"type": "failed", "error": "unreachable"}
