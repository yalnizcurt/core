"""Tests for the health_check helper module."""

from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientError
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers.health_check import (
    DEFAULT_ENDPOINT_TIMEOUT,
    DEFAULT_TCP_TIMEOUT,
    HealthCheckResult,
    async_check_endpoint,
    async_check_tcp_connection,
)
from homeassistant.util import dt as dt_util

from tests.test_util.aiohttp import AiohttpClientMocker


class TestHealthCheckResult:
    """Unit tests for HealthCheckResult."""

    def test_as_system_health_dict_ok_with_latency(self) -> None:
        """Test successful result with latency formats as 'Xms' string."""
        result = HealthCheckResult(
            ok=True,
            latency_ms=42.6,
            error=None,
            timestamp=dt_util.utcnow(),
        )
        assert result.as_system_health_dict() == "43ms"

    def test_as_system_health_dict_ok_without_latency(self) -> None:
        """Test successful result without latency returns 'ok'."""
        result = HealthCheckResult(
            ok=True,
            latency_ms=None,
            error=None,
            timestamp=dt_util.utcnow(),
        )
        assert result.as_system_health_dict() == "ok"

    def test_as_system_health_dict_failure_with_error(self) -> None:
        """Test failed result returns failure dict."""
        result = HealthCheckResult(
            ok=False,
            latency_ms=None,
            error="timeout",
            timestamp=dt_util.utcnow(),
        )
        assert result.as_system_health_dict() == {"type": "failed", "error": "timeout"}

    def test_as_system_health_dict_failure_no_error(self) -> None:
        """Test failed result with no error message uses 'unknown'."""
        result = HealthCheckResult(
            ok=False,
            latency_ms=None,
            error=None,
            timestamp=dt_util.utcnow(),
        )
        assert result.as_system_health_dict() == {
            "type": "failed",
            "error": "unknown",
        }

    def test_frozen_dataclass(self) -> None:
        """Test that HealthCheckResult is immutable."""
        result = HealthCheckResult(
            ok=True,
            latency_ms=10.0,
            error=None,
            timestamp=dt_util.utcnow(),
        )
        with pytest.raises(AttributeError):
            result.ok = False  # type: ignore[misc]

    def test_timestamp_is_datetime(self) -> None:
        """Test that timestamp is a datetime object."""
        ts = dt_util.utcnow()
        result = HealthCheckResult(ok=True, latency_ms=1.0, error=None, timestamp=ts)
        assert isinstance(result.timestamp, datetime)
        assert result.timestamp == ts


class TestAsyncCheckEndpoint:
    """Tests for async_check_endpoint."""

    async def test_reachable_endpoint_returns_ok(
        self,
        hass: HomeAssistant,
        aioclient_mock: AiohttpClientMocker,
    ) -> None:
        """Test that a reachable endpoint returns ok=True with latency."""
        aioclient_mock.get("http://example.com/api", text="OK")

        result = await async_check_endpoint(hass, "http://example.com/api")

        assert result.ok is True
        assert result.latency_ms is not None
        assert result.latency_ms >= 0
        assert result.error is None
        assert isinstance(result.timestamp, datetime)

    async def test_client_error_returns_unreachable(
        self,
        hass: HomeAssistant,
        aioclient_mock: AiohttpClientMocker,
    ) -> None:
        """Test that a ClientError results in unreachable failure."""
        aioclient_mock.get("http://example.com/api", exc=ClientError)

        result = await async_check_endpoint(hass, "http://example.com/api")

        assert result.ok is False
        assert result.latency_ms is None
        assert result.error == "unreachable"

    async def test_timeout_returns_timeout_error(
        self,
        hass: HomeAssistant,
        aioclient_mock: AiohttpClientMocker,
    ) -> None:
        """Test that a timeout results in timeout failure."""
        aioclient_mock.get("http://example.com/api", exc=asyncio.TimeoutError)

        result = await async_check_endpoint(hass, "http://example.com/api")

        assert result.ok is False
        assert result.latency_ms is None
        assert result.error == "timeout"

    async def test_4xx_response_is_reachable(
        self,
        hass: HomeAssistant,
        aioclient_mock: AiohttpClientMocker,
    ) -> None:
        """Test that a 4xx response counts as reachable (endpoint is up)."""
        aioclient_mock.get("http://example.com/api", status=403, text="Forbidden")

        result = await async_check_endpoint(hass, "http://example.com/api")

        assert result.ok is True
        assert result.latency_ms is not None

    async def test_default_timeout_value(self) -> None:
        """Test that the default timeout constant is reasonable."""
        assert DEFAULT_ENDPOINT_TIMEOUT == 5.0


class TestAsyncCheckTcpConnection:
    """Tests for async_check_tcp_connection."""

    async def test_successful_connection_returns_ok(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Test that a successful TCP connection returns ok=True with latency."""
        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock(return_value=None)

        with patch(
            "asyncio.open_connection",
            return_value=(MagicMock(), mock_writer),
        ):
            result = await async_check_tcp_connection("127.0.0.1", 8123)

        assert result.ok is True
        assert result.latency_ms is not None
        assert result.latency_ms >= 0
        assert result.error is None

    async def test_os_error_returns_unreachable(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Test that an OSError results in unreachable failure."""
        with patch(
            "asyncio.open_connection",
            side_effect=OSError("Connection refused"),
        ):
            result = await async_check_tcp_connection("127.0.0.1", 9999)

        assert result.ok is False
        assert result.latency_ms is None
        assert result.error == "unreachable"

    async def test_timeout_returns_timeout_error(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Test that a timeout results in timeout failure."""
        with patch(
            "asyncio.open_connection",
            side_effect=asyncio.TimeoutError,
        ):
            result = await async_check_tcp_connection("127.0.0.1", 8123)

        assert result.ok is False
        assert result.latency_ms is None
        assert result.error == "timeout"

    async def test_default_timeout_value(self) -> None:
        """Test that the default TCP timeout constant is reasonable."""
        assert DEFAULT_TCP_TIMEOUT == 5.0
