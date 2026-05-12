"""WhisperCppLocalASRClient のユニットテスト。httpx と _transcode_to_wav はモックで代替する。

BE-016: _transcode_to_wav の単体テストも含む。
  - 正常系: subprocess が WAV バイト列を返す
  - エラー系: 非ゼロ終了コード → ASRError
  - WAV ショートサーキット: content_type が audio/wav の場合はトランスコードしない
  - 空テキストゲーティング: {"text": ""} → ASRError
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.asr.errors import ASRError
from app.infrastructure.asr.types import AudioPayload, TranscribeParams
from app.infrastructure.asr.whisper_cpp_client import (
    WhisperCppLocalASRClient,
    _transcode_to_wav,
)

# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------


def _make_audio(
    content: bytes = b"test-audio",
    content_type: str = "audio/webm;codecs=opus",
) -> AudioPayload:
    return AudioPayload(audio_bytes=content, content_type=content_type)


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


def _stub_transcode(return_bytes: bytes = b"fake-wav") -> AsyncMock:
    """_transcode_to_wav を既知の WAV バイト列を返すスタブに差し替える。"""
    return AsyncMock(return_value=return_bytes)


# ---------------------------------------------------------------------------
# _transcode_to_wav 単体テスト (BE-016)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transcode_wav_passthrough() -> None:
    """content_type が audio/wav の場合はトランスコードせずそのまま返す。"""
    original = b"RIFF....WAV"
    result = await _transcode_to_wav(original, "audio/wav")
    assert result is original


@pytest.mark.asyncio
async def test_transcode_wav_passthrough_with_params() -> None:
    """audio/wav;codecs=... 形式でも WAV ショートサーキットが動作する。"""
    original = b"RIFF....WAV"
    result = await _transcode_to_wav(original, "audio/wav;codecs=pcm")
    assert result is original


@pytest.mark.asyncio
async def test_transcode_success() -> None:
    """正常系: ffmpeg プロセスが 0 で終了し WAV バイト列を返す。"""
    fake_wav = b"RIFF\x00\x00\x00\x00WAVEfmt "
    fake_proc = AsyncMock()
    fake_proc.returncode = 0
    fake_proc.communicate = AsyncMock(return_value=(fake_wav, b""))

    with patch(
        "app.infrastructure.asr.whisper_cpp_client.asyncio.create_subprocess_exec",
        return_value=fake_proc,
    ):
        result = await _transcode_to_wav(b"webm-bytes", "audio/webm;codecs=opus")

    assert result == fake_wav


@pytest.mark.asyncio
async def test_transcode_nonzero_exit_raises_asr_error() -> None:
    """ffmpeg が非ゼロ終了コードを返した場合は ASRError を送出する。"""
    fake_proc = AsyncMock()
    fake_proc.returncode = 1
    fake_proc.communicate = AsyncMock(return_value=(b"", b"some error"))

    with (
        patch(
            "app.infrastructure.asr.whisper_cpp_client.asyncio.create_subprocess_exec",
            return_value=fake_proc,
        ),
        pytest.raises(ASRError) as exc_info,
    ):
        await _transcode_to_wav(b"bad-audio", "audio/webm;codecs=opus")

    assert "transcode failed" in str(exc_info.value)
    assert exc_info.value.timeout is False


@pytest.mark.asyncio
async def test_transcode_ffmpeg_not_found_raises_asr_error() -> None:
    """ffmpeg バイナリが存在しない場合は ASRError を送出する。"""
    with (
        patch(
            "app.infrastructure.asr.whisper_cpp_client.asyncio.create_subprocess_exec",
            side_effect=FileNotFoundError("ffmpeg not found"),
        ),
        pytest.raises(ASRError) as exc_info,
    ):
        await _transcode_to_wav(b"audio", "audio/webm")

    assert "ffmpeg binary not found" in str(exc_info.value)


# ---------------------------------------------------------------------------
# WhisperCppLocalASRClient.transcribe テスト
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transcribe_success() -> None:
    """正常系: 200 が返れば TranscribeResponse を返す。"""
    resp = _make_http_response(status=200, json_body={"text": " 患者は良好です。"})
    mock_cls = MagicMock(return_value=_make_async_client_mock(resp))

    with (
        patch(
            "app.infrastructure.asr.whisper_cpp_client._transcode_to_wav",
            _stub_transcode(),
        ),
        patch("app.infrastructure.asr.whisper_cpp_client.httpx.AsyncClient", mock_cls),
    ):
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

    with (
        patch(
            "app.infrastructure.asr.whisper_cpp_client._transcode_to_wav",
            _stub_transcode(),
        ),
        patch("app.infrastructure.asr.whisper_cpp_client.httpx.AsyncClient", mock_cls),
    ):
        client = WhisperCppLocalASRClient()
        result = await client.transcribe(_make_audio())

    assert result.text == "テスト"
    assert result.duration_seconds == pytest.approx(5.0)


@pytest.mark.asyncio
async def test_transcribe_empty_text_raises_asr_error() -> None:
    """whisper-server が {"text": ""} を返した場合は ASRError を送出する。

    BE-016 空テキストゲーティング:
    whisper-server は音声デコード失敗時も HTTP 200 で空テキストを返すため
    ASRError に変換して 503 を返す。
    """
    resp = _make_http_response(status=200, json_body={"text": ""})
    mock_cls = MagicMock(return_value=_make_async_client_mock(resp))

    with (
        patch(
            "app.infrastructure.asr.whisper_cpp_client._transcode_to_wav",
            _stub_transcode(),
        ),
        patch("app.infrastructure.asr.whisper_cpp_client.httpx.AsyncClient", mock_cls),
        pytest.raises(ASRError) as exc_info,
    ):
        client = WhisperCppLocalASRClient()
        await client.transcribe(_make_audio())

    assert "empty text" in str(exc_info.value)
    # 音声バイト列が例外文字列に含まれないことを確認
    assert b"test-audio" not in str(exc_info.value).encode()


@pytest.mark.asyncio
async def test_transcribe_whitespace_only_text_raises_asr_error() -> None:
    """空白のみのテキストも strip 後に空になるため ASRError を送出する (BE-016)。"""
    resp = _make_http_response(status=200, json_body={"text": "   "})
    mock_cls = MagicMock(return_value=_make_async_client_mock(resp))

    with (
        patch(
            "app.infrastructure.asr.whisper_cpp_client._transcode_to_wav",
            _stub_transcode(),
        ),
        patch("app.infrastructure.asr.whisper_cpp_client.httpx.AsyncClient", mock_cls),
        pytest.raises(ASRError),
    ):
        client = WhisperCppLocalASRClient()
        await client.transcribe(_make_audio())


@pytest.mark.asyncio
async def test_transcribe_non_200_raises_asr_error() -> None:
    """非200 レスポンスは ASRError を送出する。"""
    resp = _make_http_response(status=503, json_body={})
    mock_cls = MagicMock(return_value=_make_async_client_mock(resp))

    with (
        patch(
            "app.infrastructure.asr.whisper_cpp_client._transcode_to_wav",
            _stub_transcode(),
        ),
        patch("app.infrastructure.asr.whisper_cpp_client.httpx.AsyncClient", mock_cls),
        pytest.raises(ASRError) as exc_info,
    ):
        client = WhisperCppLocalASRClient()
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

    with (
        patch(
            "app.infrastructure.asr.whisper_cpp_client._transcode_to_wav",
            _stub_transcode(),
        ),
        patch("app.infrastructure.asr.whisper_cpp_client.httpx.AsyncClient", mock_cls),
        pytest.raises(ASRError) as exc_info,
    ):
        client = WhisperCppLocalASRClient()
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

    with (
        patch(
            "app.infrastructure.asr.whisper_cpp_client._transcode_to_wav",
            _stub_transcode(),
        ),
        patch("app.infrastructure.asr.whisper_cpp_client.httpx.AsyncClient", mock_cls),
        pytest.raises(ASRError) as exc_info,
    ):
        client = WhisperCppLocalASRClient()
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

    with (
        patch(
            "app.infrastructure.asr.whisper_cpp_client._transcode_to_wav",
            _stub_transcode(),
        ),
        patch("app.infrastructure.asr.whisper_cpp_client.httpx.AsyncClient", mock_cls),
    ):
        client = WhisperCppLocalASRClient()
        params = TranscribeParams(language="ja")
        await client.transcribe(_make_audio(), params)

    call_kwargs = client_ctx.post.call_args.kwargs
    assert call_kwargs["data"]["language"] == "ja"


@pytest.mark.asyncio
async def test_transcribe_wav_file_sent_to_whisper() -> None:
    """トランスコード後の WAV バイト列が audio.wav として whisper-server に送られる。"""
    fake_wav = b"RIFF\x00\x00\x00\x00WAVEfmt "
    resp = _make_http_response(status=200, json_body={"text": "テスト結果"})
    client_ctx = AsyncMock()
    client_ctx.__aenter__ = AsyncMock(return_value=client_ctx)
    client_ctx.__aexit__ = AsyncMock(return_value=False)
    client_ctx.post = AsyncMock(return_value=resp)
    mock_cls = MagicMock(return_value=client_ctx)

    with (
        patch(
            "app.infrastructure.asr.whisper_cpp_client._transcode_to_wav",
            _stub_transcode(fake_wav),
        ),
        patch("app.infrastructure.asr.whisper_cpp_client.httpx.AsyncClient", mock_cls),
    ):
        client = WhisperCppLocalASRClient()
        await client.transcribe(_make_audio())

    call_kwargs = client_ctx.post.call_args.kwargs
    file_tuple = call_kwargs["files"]["file"]
    # (filename, bytes, content_type) の形式で送られていることを確認
    assert file_tuple[0] == "audio.wav"
    assert file_tuple[1] == fake_wav
    assert file_tuple[2] == "audio/wav"


# ---------------------------------------------------------------------------
# WhisperCppLocalASRClient.ping テスト
# ---------------------------------------------------------------------------


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
