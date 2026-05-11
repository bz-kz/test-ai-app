"""OllamaLocalLLMClient のユニットテスト。httpx はモックで代替する。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.llm.config import LLM_MODEL
from app.infrastructure.llm.errors import InferenceError
from app.infrastructure.llm.ollama_client import OllamaLocalLLMClient
from app.infrastructure.llm.types import GenerateParams


def _make_http_response(*, status: int = 200, json_body: dict) -> MagicMock:
    """httpx.Response の最小限のモックを返す。"""
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_body
    return resp


def _make_async_client_mock(response: MagicMock) -> MagicMock:
    """httpx.AsyncClient のコンテキストマネージャモックを返す。"""
    client_ctx = AsyncMock()
    client_ctx.__aenter__ = AsyncMock(return_value=client_ctx)
    client_ctx.__aexit__ = AsyncMock(return_value=False)
    client_ctx.post = AsyncMock(return_value=response)
    client_ctx.get = AsyncMock(return_value=response)
    return client_ctx


@pytest.mark.asyncio
async def test_generate_success() -> None:
    """正常系: 200 が返れば GenerateResponse を返す。"""
    resp = _make_http_response(status=200, json_body={"response": "draft text", "done": True})
    mock_cls = MagicMock(return_value=_make_async_client_mock(resp))

    with patch("app.infrastructure.llm.ollama_client.httpx.AsyncClient", mock_cls):
        client = OllamaLocalLLMClient(base_url="http://llm:11434", model=LLM_MODEL, timeout_s=60)
        result = await client.generate("draft prompt")

    assert result.text == "draft text"


@pytest.mark.asyncio
async def test_generate_non_200_raises_inference_error() -> None:
    """非200 レスポンスは InferenceError を送出する。"""
    resp = _make_http_response(status=503, json_body={})
    mock_cls = MagicMock(return_value=_make_async_client_mock(resp))

    with patch("app.infrastructure.llm.ollama_client.httpx.AsyncClient", mock_cls):
        client = OllamaLocalLLMClient()
        with pytest.raises(InferenceError) as exc_info:
            await client.generate("some prompt")

    # raw_prompt が例外文字列に含まれないことを確認
    assert "some prompt" not in str(exc_info.value)
    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_generate_timeout_raises_inference_error() -> None:
    """タイムアウトは InferenceError を送出する。"""
    import httpx

    client_ctx = AsyncMock()
    client_ctx.__aenter__ = AsyncMock(return_value=client_ctx)
    client_ctx.__aexit__ = AsyncMock(return_value=False)
    client_ctx.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
    mock_cls = MagicMock(return_value=client_ctx)

    with patch("app.infrastructure.llm.ollama_client.httpx.AsyncClient", mock_cls):
        client = OllamaLocalLLMClient()
        with pytest.raises(InferenceError) as exc_info:
            await client.generate("sensitive prompt data")

    assert "sensitive prompt data" not in str(exc_info.value)
    assert exc_info.value.status_code is None


@pytest.mark.asyncio
async def test_ping_success() -> None:
    """ping() が True を返すことを確認する。"""
    resp = _make_http_response(status=200, json_body={"models": []})
    mock_cls = MagicMock(return_value=_make_async_client_mock(resp))

    with patch("app.infrastructure.llm.ollama_client.httpx.AsyncClient", mock_cls):
        client = OllamaLocalLLMClient()
        result = await client.ping()

    assert result is True


@pytest.mark.asyncio
async def test_ping_failure_returns_false() -> None:
    """ping() が接続エラーのとき False を返す（例外を送出しない）。"""
    import httpx

    client_ctx = AsyncMock()
    client_ctx.__aenter__ = AsyncMock(return_value=client_ctx)
    client_ctx.__aexit__ = AsyncMock(return_value=False)
    client_ctx.get = AsyncMock(side_effect=httpx.ConnectError("unreachable"))
    mock_cls = MagicMock(return_value=client_ctx)

    with patch("app.infrastructure.llm.ollama_client.httpx.AsyncClient", mock_cls):
        client = OllamaLocalLLMClient()
        result = await client.ping()

    assert result is False


@pytest.mark.asyncio
async def test_generate_with_params_forwarded() -> None:
    """GenerateParams の値が Ollama ペイロードに反映されることを確認する。"""
    resp = _make_http_response(status=200, json_body={"response": "ok", "done": True})
    client_ctx = AsyncMock()
    client_ctx.__aenter__ = AsyncMock(return_value=client_ctx)
    client_ctx.__aexit__ = AsyncMock(return_value=False)
    client_ctx.post = AsyncMock(return_value=resp)
    mock_cls = MagicMock(return_value=client_ctx)

    with patch("app.infrastructure.llm.ollama_client.httpx.AsyncClient", mock_cls):
        client = OllamaLocalLLMClient()
        params = GenerateParams(temperature=0.2, max_tokens=500)
        result = await client.generate("q", params)

    assert result.text == "ok"
    # post に渡された kwargs を検証する
    call_kwargs = client_ctx.post.call_args.kwargs
    options = call_kwargs["json"]["options"]
    assert options["temperature"] == pytest.approx(0.2)
    assert options["num_predict"] == 500
