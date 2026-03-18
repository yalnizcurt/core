"""Tests for the RESTful integration system health."""

from __future__ import annotations

from aiohttp import ClientError

from homeassistant.components.rest.const import DOMAIN
from homeassistant.components.rest.system_health import system_health_info
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import get_system_health_info
from tests.test_util.aiohttp import AiohttpClientMocker

_REST_CONFIG = {
    DOMAIN: [
        {
            "resource": "http://example.com/api",
            "method": "GET",
            "verify_ssl": "false",
            "sensor": [
                {
                    "name": "test_sensor",
                    "value_template": "{{ value }}",
                }
            ],
        }
    ]
}


async def test_rest_system_health_reachable(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test REST system health when endpoint is reachable."""
    aioclient_mock.get("http://example.com/api", text="hello")

    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, DOMAIN, _REST_CONFIG)
    await hass.async_block_till_done()
    assert await async_setup_component(hass, "system_health", {})
    await hass.async_block_till_done()

    info = await get_system_health_info(hass, DOMAIN)

    assert info["configured_resources"] == 1
    assert info["reachable_resources"] == 1
    assert info["unreachable_resources"] == 0
    # The endpoint value is a latency string like "Xms" when reachable.
    assert str(info["resource_0_endpoint"]).endswith("ms")
    assert info["resource_0_last_update"] == "ok"


async def test_rest_system_health_unreachable(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test REST system health when endpoint is unreachable."""
    # Allow the initial REST setup to succeed so the component registers.
    aioclient_mock.get("http://example.com/api", text="hello")

    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, DOMAIN, _REST_CONFIG)
    await hass.async_block_till_done()

    # Now simulate the endpoint being unreachable for the health check.
    aioclient_mock.clear_requests()
    aioclient_mock.get("http://example.com/api", exc=ClientError)

    assert await async_setup_component(hass, "system_health", {})
    await hass.async_block_till_done()

    info = await get_system_health_info(hass, DOMAIN)

    assert info["configured_resources"] == 1
    assert info["unreachable_resources"] == 1
    assert info["reachable_resources"] == 0
    assert info["resource_0_endpoint"] == {"type": "failed", "error": "unreachable"}


async def test_rest_system_health_no_resources(
    hass: HomeAssistant,
) -> None:
    """Test REST system_health_info returns zero counts when no resources are configured."""
    # Call system_health_info directly without setting up the REST component.
    # hass.data.get(DOMAIN, {}) returns {} so REST_DATA defaults to an empty
    # list – this exercises the defensive guard path in the function.
    info = await system_health_info(hass)

    assert info["configured_resources"] == 0
    assert info["reachable_resources"] == 0
    assert info["unreachable_resources"] == 0
