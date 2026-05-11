"""WhisperCppLocalASRClient のユニットテスト。httpx はモックで代替する。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.asr.errors import ASRError
from app.infrastructure.asr.types import AudioPayload, TranscribeParams
from app.infrastructure.asr.whisper_cpp_client import WhisperCppLocalASRClient


def _make_audio(content: bytes = b"test-audio") -> AudioPayload:
    return AudioPayload(audio_bytes=content, content_type="audio/webm;codecs=opus")


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
async def test_transcribe_success() -> None:
    """正常系: 200 が返れば TranscribeResponse を返す。"""
    resp = _make_http_response(status=200, json_body={"text": " 患者は良好です。"})
    mock_cls = MagicMock(return_value=_make_async_client_mock(resp))

    with patch("app.infrastructure.asr.whisper_cpp_client.httpx.AsyncClient", mock_cls):
        client = WhisperCppLocalASRClient(base_url="http://asr:8080")
        result = await client.transcribe(_make_audio())

    # text はストリップされる
    assert result.text == "患者は良好です。"
    assert result.duration_seconds is None


@pytest.mark.asyncio
async def test_transcribe_success_with_duration() -> None:
    """duration フィールドがある場合は duration_seconds に変換する。"""
    resp = _make_http_response(status=200, json_body={"text": "テスト", "duration": 5000})
    mock_cls = MagicMock(return_value=_make_async_client_mock(resp))

    with patch("app.infrastructure.asr.whisper_cpp_client.httpx.AsyncClient", mock_cls):
        client = WhisperCppLocalASRClient()
        result = await client.transcribe(_make_audio())

    assert result.text == "テスト"
    assert result.duration_seconds == pytest.approx(5.0)


@pytest.mark.asyncio
async def test_transcribe_non_200_raises_asr_error() -> None:
    """非200 レスポンスは ASRError を送出する。"""
    resp = _make_http_response(status=503, json_body={})
    mock_cls = MagicMock(return_value=_make_async_client_mock(resp))

    with patch("app.infrastructure.asr.whisper_cpp_client.httpx.AsyncClient", mock_cls):
        client = WhisperCppLocalASRClient()
        with pytest.raises(ASRError) as exc_info:
            await client.transcribe(_make_audio())

    assert exc_info.value.status_code == 503
    # 音声バイト列が例外文字列に含まれないことを確認
    assert b"test-audio" not in str(exc_info.value).encode()
    assert exc_info.value.timeout is False


@pytest.mark.asyncio
async def test_transcribe_timeout_raises_asr_error() -> None:
    """タイムアウトは timeout=True の ASRError を送出する。"""
    import httpx

    client_ctx = AsyncMock()
    client_ctx.__aenter__ = AsyncMock(return_value=client_ctx)
    client_ctx.__aexit__ = AsyncMock(return_value=False)
    client_ctx.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
    mock_cls = MagicMock(return_value=client_ctx)

    with patch("app.infrastructure.asr.whisper_cpp_client.httpx.AsyncClient", mock_cls):
        client = WhisperCppLocalASRClient()
        with pytest.raises(ASRError) as exc_info:
            await client.transcribe(_make_audio(b"sensitive audio"))

    assert exc_info.value.timeout is True
    # 音声バイト列が例外文字列に含まれないことを確認
    assert b"sensitive audio" not in str(exc_info.value).encode()


@pytest.mark.asyncio
async def test_transcribe_network_error_raises_asr_error() -> None:
    """ネットワークエラーは ASRError を送出する。"""
    import httpx

    client_ctx = AsyncMock()
    client_ctx.__aenter__ = AsyncMock(return_value=client_ctx)
    client_ctx.__aexit__ = AsyncMock(return_value=False)
    client_ctx.post = AsyncMock(side_effect=httpx.ConnectError("unreachable"))
    mock_cls = MagicMock(return_value=client_ctx)

    with patch("app.infrastructure.asr.whisper_cpp_client.httpx.AsyncClient", mock_cls):
        client = WhisperCppLocalASRClient()
        with pytest.raises(ASRError) as exc_info:
            await client.transcribe(_make_audio())

    assert exc_info.value.timeout is False
    assert exc_info.value.status_code is None


@pytest.mark.asyncio
async def test_transcribe_language_param_forwarded() -> None:
    """TranscribeParams.language が whisper-server に渡されることを確認する。"""
    resp = _make_http_response(status=200, json_body={"text": "テスト"})
    client_ctx = AsyncMock()
    client_ctx.__aenter__ = AsyncMock(return_value=client_ctx)
    client_ctx.__aexit__ = AsyncMock(return_value=False)
    client_ctx.post = AsyncMock(return_value=resp)
    mock_cls = MagicMock(return_value=client_ctx)

    with patch("app.infrastructure.asr.whisper_cpp_client.httpx.AsyncClient", mock_cls):
        client = WhisperCppLocalASRClient()
        params = TranscribeParams(language="ja")
        await client.transcribe(_make_audio(), params)

    call_kwargs = client_ctx.post.call_args.kwargs
    assert call_kwargs["data"]["language"] == "ja"


@pytest.mark.asyncio
async def test_ping_success() -> None:
    """ping() が True を返すことを確認する。"""
    resp = _make_http_response(status=200, json_body={})
    mock_cls = MagicMock(return_value=_make_async_client_mock(resp))

    with patch("app.infrastructure.asr.whisper_cpp_client.httpx.AsyncClient", mock_cls):
        client = WhisperCppLocalASRClient()
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

    with patch("app.infrastructure.asr.whisper_cpp_client.httpx.AsyncClient", mock_cls):
        client = WhisperCppLocalASRClient()
        result = await client.ping()

    assert result is False


@pytest.mark.asyncio
async def test_ping_non_200_returns_false() -> None:
    """ping() が非200 のとき False を返す。"""
    resp = _make_http_response(status=503, json_body={})
    mock_cls = MagicMock(return_value=_make_async_client_mock(resp))

    with patch("app.infrastructure.asr.whisper_cpp_client.httpx.AsyncClient", mock_cls):
        client = WhisperCppLocalASRClient()
        result = await client.ping()

    assert result is False
