"""Tests for the HTTP integration system health."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.http import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import get_system_health_info


async def test_http_system_health_server_reachable(
    hass: HomeAssistant,
) -> None:
    """Test HTTP system health when the server TCP port is accepting connections."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    assert await async_setup_component(hass, "system_health", {})
    await hass.async_block_till_done()

    mock_writer = MagicMock()
    mock_writer.close = MagicMock()
    mock_writer.wait_closed = AsyncMock(return_value=None)

    with patch(
        "asyncio.open_connection",
        return_value=(MagicMock(), mock_writer),
    ):
        info = await get_system_health_info(hass, DOMAIN)

    assert "server_port" in info
    assert info["ssl_active"] is False
    # Result should be a latency string like "Xms".
    assert str(info["server_reachable"]).endswith("ms")


async def test_http_system_health_server_unreachable(
    hass: HomeAssistant,
) -> None:
    """Test HTTP system health when the server TCP port is not connectable."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    assert await async_setup_component(hass, "system_health", {})
    await hass.async_block_till_done()

    with patch(
        "asyncio.open_connection",
        side_effect=OSError("Connection refused"),
    ):
        info = await get_system_health_info(hass, DOMAIN)

    assert info["server_reachable"] == {"type": "failed", "error": "unreachable"}


async def test_http_system_health_server_timeout(
    hass: HomeAssistant,
) -> None:
    """Test HTTP system health when the connection to server times out."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    assert await async_setup_component(hass, "system_health", {})
    await hass.async_block_till_done()

    with patch(
        "asyncio.open_connection",
        side_effect=asyncio.TimeoutError,
    ):
        info = await get_system_health_info(hass, DOMAIN)

    assert info["server_reachable"] == {"type": "failed", "error": "timeout"}
