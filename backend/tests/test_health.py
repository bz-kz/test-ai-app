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
    """Postgres と LLM と ASR が全て到達可能なとき 200 を返す (BE-014)。"""
    with (
        patch("asyncpg.connect", _make_asyncpg_mock(succeed=True)),
        patch(
            "app.infrastructure.llm.ollama_client.OllamaLocalLLMClient.ping",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "app.infrastructure.asr.whisper_cpp_client.WhisperCppLocalASRClient.ping",
            new_callable=AsyncMock,
            return_value=True,
        ),
    ):
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["postgres"] is True
    assert body["llm"] is True
    assert body["asr"] is True


@pytest.mark.asyncio
async def test_health_postgres_down() -> None:
    """Postgres が到達不能なとき 503 を返す。"""
    with (
        patch("asyncpg.connect", _make_asyncpg_mock(succeed=False)),
        patch(
            "app.infrastructure.llm.ollama_client.OllamaLocalLLMClient.ping",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "app.infrastructure.asr.whisper_cpp_client.WhisperCppLocalASRClient.ping",
            new_callable=AsyncMock,
            return_value=True,
        ),
    ):
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
        patch(
            "app.infrastructure.llm.ollama_client.OllamaLocalLLMClient.ping",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "app.infrastructure.asr.whisper_cpp_client.WhisperCppLocalASRClient.ping",
            new_callable=AsyncMock,
            return_value=True,
        ),
    ):
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/health")

    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["llm"] is False


@pytest.mark.asyncio
async def test_health_asr_down() -> None:
    """ASR が到達不能なとき 503 を返す (BE-014)。"""
    with (
        patch("asyncpg.connect", _make_asyncpg_mock(succeed=True)),
        patch(
            "app.infrastructure.llm.ollama_client.OllamaLocalLLMClient.ping",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "app.infrastructure.asr.whisper_cpp_client.WhisperCppLocalASRClient.ping",
            new_callable=AsyncMock,
            return_value=False,
        ),
    ):
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/health")

    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["asr"] is False
