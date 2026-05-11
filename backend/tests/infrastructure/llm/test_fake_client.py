"""FakeLocalLLMClient のユニットテスト。決定論的振る舞いと force_error を検証する。"""

from __future__ import annotations

import pytest

from app.infrastructure.llm.errors import InferenceError
from app.infrastructure.llm.fake_client import FakeLocalLLMClient
from app.infrastructure.llm.types import GenerateParams


@pytest.mark.asyncio
async def test_fake_generate_default_response() -> None:
    """フィクスチャに未登録のプロンプトはデフォルト応答を返す。"""
    client = FakeLocalLLMClient()
    result = await client.generate("unknown prompt")
    assert result.text == FakeLocalLLMClient.DEFAULT_RESPONSE
    assert client.generate_call_count == 1


@pytest.mark.asyncio
async def test_fake_generate_fixture_map() -> None:
    """フィクスチャマップに登録済みのプロンプトは対応する応答を返す。"""
    client = FakeLocalLLMClient(fixture_map={"hello": "world"})
    result = await client.generate("hello")
    assert result.text == "world"


@pytest.mark.asyncio
async def test_fake_generate_force_error() -> None:
    """force_error=True のとき InferenceError を送出する。"""
    client = FakeLocalLLMClient(force_error=True)
    with pytest.raises(InferenceError):
        await client.generate("any prompt")


@pytest.mark.asyncio
async def test_fake_stream_yields_chunks() -> None:
    """stream() が Chunk を yield し、最終チャンクの done=True を確認する。"""
    client = FakeLocalLLMClient(fixture_map={"q": "answer"})
    chunks = []
    async for chunk in await client.stream("q"):
        chunks.append(chunk)
    assert len(chunks) == 2  # noqa: PLR2004 — テスト固有の定数
    assert chunks[0].text == "answer"
    assert chunks[0].done is False
    assert chunks[1].done is True
    assert client.stream_call_count == 1


@pytest.mark.asyncio
async def test_fake_stream_force_error() -> None:
    """force_error=True のとき stream も InferenceError を送出する。"""
    client = FakeLocalLLMClient(force_error=True)
    with pytest.raises(InferenceError):
        async for _ in await client.stream("prompt"):
            pass


@pytest.mark.asyncio
async def test_fake_ping_true() -> None:
    client = FakeLocalLLMClient(ping_result=True)
    result = await client.ping()
    assert result is True
    assert client.ping_call_count == 1


@pytest.mark.asyncio
async def test_fake_ping_false() -> None:
    client = FakeLocalLLMClient(ping_result=False)
    result = await client.ping()
    assert result is False


@pytest.mark.asyncio
async def test_fake_generate_with_params() -> None:
    """GenerateParams を渡しても正常に動作することを確認する。"""
    client = FakeLocalLLMClient()
    params = GenerateParams(temperature=0.5, max_tokens=100)
    result = await client.generate("test", params)
    assert result.text == FakeLocalLLMClient.DEFAULT_RESPONSE
