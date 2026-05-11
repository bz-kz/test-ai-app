"""ヘルスエンドポイントのユニットテスト。外部依存はモックで代替する。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app


def _make_asyncpg_mock(*, succeed: bool) -> MagicMock:
    """asyncpg.connect の振る舞いを制御するモックを返す。"""
    mock = AsyncMock()
    if not succeed:
        mock.side_effect = ConnectionRefusedError("db unreachable")
    else:
        conn = AsyncMock()
        conn.close = AsyncMock()
        mock.return_value = conn
    return mock


@pytest.mark.asyncio
async def test_health_all_ok() -> None:
    """Postgres と LLM の両方が到達可能なとき 200 を返す。"""
    with (
        patch("asyncpg.connect", _make_asyncpg_mock(succeed=True)),
        patch("httpx.AsyncClient") as mock_client_cls,
    ):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_ctx.get = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_ctx

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["postgres"] is True
    assert body["llm"] is True


@pytest.mark.asyncio
async def test_health_postgres_down() -> None:
    """Postgres が到達不能なとき 503 を返す。"""
    with (
        patch("asyncpg.connect", _make_asyncpg_mock(succeed=False)),
        patch("httpx.AsyncClient") as mock_client_cls,
    ):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_ctx.get = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_ctx

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/health")

    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["postgres"] is False


@pytest.mark.asyncio
async def test_health_llm_down() -> None:
    """LLM が到達不能なとき 503 を返す。"""
    with (
        patch("asyncpg.connect", _make_asyncpg_mock(succeed=True)),
        patch("httpx.AsyncClient") as mock_client_cls,
    ):
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_ctx.get = AsyncMock(side_effect=ConnectionRefusedError("llm unreachable"))
        mock_client_cls.return_value = mock_ctx

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/health")

    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["llm"] is False
