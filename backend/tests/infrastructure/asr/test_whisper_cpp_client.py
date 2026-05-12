"""WhisperCppLocalASRClient のユニットテスト。httpx と _transcode_to_wav はモックで代替する。

BE-016: _transcode_to_wav の単体テストも含む。
  - 正常系: subprocess が WAV バイト列を返す
  - エラー系: 非ゼロ終了コード → ASRError
  - WAV ショートサーキット: content_type が audio/wav の場合はトランスコードしない
  - 空テキストゲーティング: {"text": ""} → ASRError

BE-017: _slice_wav_to_chunks および stream_transcribe の単体テストを追加。
  - _slice_wav_to_chunks: チャンク数・バイト整合・最終チャンク短縮・非WAVヘッダーエラー
  - stream_transcribe: 正常系チャンク列・空テキストゲーティング・mid-stream エラー
"""

from __future__ import annotations

import io
import wave
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.asr.errors import ASRError
from app.infrastructure.asr.types import AudioPayload, TranscribeChunk, TranscribeParams
from app.infrastructure.asr.whisper_cpp_client import (
    WhisperCppLocalASRClient,
    _slice_wav_to_chunks,
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


def _make_wav(
    duration_s: float,
    framerate: int = 16000,
    n_channels: int = 1,
    sampwidth: int = 2,
) -> bytes:
    """指定秒数の無音 WAV バイト列を生成する (テスト専用)。"""
    n_frames = int(duration_s * framerate)
    pcm = bytes(n_frames * n_channels * sampwidth)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(n_channels)
        w.setsampwidth(sampwidth)
        w.setframerate(framerate)
        w.writeframes(pcm)
    return buf.getvalue()


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
# _slice_wav_to_chunks 単体テスト (BE-017)
# ---------------------------------------------------------------------------


def test_slice_wav_60s_into_6_chunks_at_10s() -> None:
    """60s WAV を chunk_seconds=10 で分割すると 6 チャンクになる。"""
    wav = _make_wav(60.0)
    chunks = _slice_wav_to_chunks(wav, chunk_seconds=10)
    assert len(chunks) == 6


def test_slice_wav_25s_into_3_chunks() -> None:
    """25s WAV を chunk_seconds=10 で分割すると 3 チャンク (10/10/5) になる。"""
    wav = _make_wav(25.0)
    chunks = _slice_wav_to_chunks(wav, chunk_seconds=10)
    assert len(chunks) == 3


def test_slice_wav_5s_into_1_chunk() -> None:
    """5s WAV を chunk_seconds=10 で分割すると 1 チャンクになる。"""
    wav = _make_wav(5.0)
    chunks = _slice_wav_to_chunks(wav, chunk_seconds=10)
    assert len(chunks) == 1


def test_slice_wav_chunks_have_valid_wav_header() -> None:
    """各チャンクが有効な RIFF WAV ヘッダーを持つ。"""
    wav = _make_wav(30.0)
    chunks = _slice_wav_to_chunks(wav, chunk_seconds=10)
    assert len(chunks) == 3
    for chunk in chunks:
        assert chunk[:4] == b"RIFF"
        assert chunk[8:12] == b"WAVE"


def test_slice_wav_chunks_readable_as_wav() -> None:
    """各チャンクを wave.open で読み込めることを確認する。"""
    wav = _make_wav(30.0)
    chunks = _slice_wav_to_chunks(wav, chunk_seconds=10)
    for chunk in chunks:
        with wave.open(io.BytesIO(chunk), "rb") as w:
            assert w.getframerate() == 16000
            assert w.getnchannels() == 1
            assert w.getsampwidth() == 2


def test_slice_wav_total_frames_preserved() -> None:
    """分割後のフレーム総数が元の WAV と一致する。"""
    wav = _make_wav(25.0)
    chunks = _slice_wav_to_chunks(wav, chunk_seconds=10)

    total_frames = 0
    for chunk in chunks:
        with wave.open(io.BytesIO(chunk), "rb") as w:
            total_frames += w.getnframes()

    with wave.open(io.BytesIO(wav), "rb") as src:
        expected = src.getnframes()

    assert total_frames == expected


def test_slice_wav_non_wav_header_raises_asr_error() -> None:
    """WAV ヘッダーでないバイト列は ASRError を送出する。"""
    not_a_wav = b"NOT_A_WAV_FILE" * 100
    with pytest.raises(ASRError) as exc_info:
        _slice_wav_to_chunks(not_a_wav, chunk_seconds=10)
    assert "WAV" in str(exc_info.value) or "failed to read" in str(exc_info.value)


def test_slice_wav_stereo_raises_asr_error() -> None:
    """ステレオ WAV は ASRError を送出する (whisper-server はモノラルのみ)。"""
    wav = _make_wav(10.0, n_channels=2)
    with pytest.raises(ASRError) as exc_info:
        _slice_wav_to_chunks(wav, chunk_seconds=10)
    assert "mono" in str(exc_info.value)


def test_slice_wav_non_16khz_raises_asr_error() -> None:
    """16kHz 以外の WAV は ASRError を送出する。"""
    wav = _make_wav(10.0, framerate=44100)
    with pytest.raises(ASRError) as exc_info:
        _slice_wav_to_chunks(wav, chunk_seconds=10)
    assert "16kHz" in str(exc_info.value)


def test_slice_wav_8bit_raises_asr_error() -> None:
    """8-bit (sampwidth=1) WAV は ASRError を送出する。"""
    wav = _make_wav(10.0, sampwidth=1)
    with pytest.raises(ASRError) as exc_info:
        _slice_wav_to_chunks(wav, chunk_seconds=10)
    assert "PCM_S16LE" in str(exc_info.value) or "16-bit" in str(exc_info.value)


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
# WhisperCppLocalASRClient.stream_transcribe テスト (BE-017)
# ---------------------------------------------------------------------------


def _make_post_side_effect(texts: list[str]) -> list[MagicMock]:
    """チャンクごとに異なるテキストを返す httpx レスポンスモックのリストを生成する。"""
    return [_make_http_response(status=200, json_body={"text": t}) for t in texts]


@pytest.mark.asyncio
async def test_stream_transcribe_happy_path() -> None:
    """正常系: 30s WAV を chunk_seconds=10 で分割すると 3 チャンク + 1 完了チャンクを返す。"""
    wav_30s = _make_wav(30.0)
    chunk_texts = ["チャンク1", "チャンク2", "チャンク3"]

    call_count = 0

    async def _fake_post_chunk(
        chunk_wav: bytes, params: TranscribeParams, chunk_index: int, audio_len: int
    ) -> str:
        nonlocal call_count
        text = chunk_texts[call_count]
        call_count += 1
        return text

    client = WhisperCppLocalASRClient(stream_chunk_seconds=10)

    with (
        patch(
            "app.infrastructure.asr.whisper_cpp_client._transcode_to_wav",
            AsyncMock(return_value=wav_30s),
        ),
        patch.object(client, "_post_chunk_to_whisper", side_effect=_fake_post_chunk),
    ):
        chunks: list[TranscribeChunk] = []
        async for chunk in client.stream_transcribe(_make_audio()):
            chunks.append(chunk)

    # 3 通常チャンク + 1 完了チャンク
    assert len(chunks) == 4
    # 最初の 3 チャンクは done=False
    for i in range(3):
        assert chunks[i].done is False
        assert chunks[i].chunk_index == i
        assert chunks[i].chunk_count == 3
        assert chunks[i].text == chunk_texts[i]
    # 最後は done=True で full_text が結合されている
    assert chunks[3].done is True
    assert chunks[3].chunk_count == 3
    assert chunks[3].text == "チャンク1チャンク2チャンク3"


@pytest.mark.asyncio
async def test_stream_transcribe_empty_chunk_text_raises_asr_error() -> None:
    """チャンクで空テキストが返された場合は ASRError を送出する (BE-016 同様のゲーティング)。"""
    wav_10s = _make_wav(10.0)

    async def _fake_post_chunk_empty(
        chunk_wav: bytes, params: TranscribeParams, chunk_index: int, audio_len: int
    ) -> str:
        raise ASRError(
            f"transcribe returned empty text (chunk {chunk_index})", audio_length=audio_len
        )

    client = WhisperCppLocalASRClient(stream_chunk_seconds=10)

    with (
        patch(
            "app.infrastructure.asr.whisper_cpp_client._transcode_to_wav",
            AsyncMock(return_value=wav_10s),
        ),
        patch.object(client, "_post_chunk_to_whisper", side_effect=_fake_post_chunk_empty),
        pytest.raises(ASRError) as exc_info,
    ):
        async for _ in client.stream_transcribe(_make_audio()):
            pass

    assert "empty text" in str(exc_info.value)


@pytest.mark.asyncio
async def test_stream_transcribe_mid_stream_failure_raises_asr_error() -> None:
    """チャンク 1 でエラーが発生した場合、その時点で ASRError を送出してイテレータを停止する。"""
    wav_30s = _make_wav(30.0)
    call_count = 0

    async def _fake_post_fail_at_1(
        chunk_wav: bytes, params: TranscribeParams, chunk_index: int, audio_len: int
    ) -> str:
        nonlocal call_count
        if call_count == 1:
            raise ASRError("chunk 1 HTTP error", audio_length=audio_len)
        text = f"chunk{call_count}"
        call_count += 1
        return text

    client = WhisperCppLocalASRClient(stream_chunk_seconds=10)

    collected: list[TranscribeChunk] = []
    with (
        patch(
            "app.infrastructure.asr.whisper_cpp_client._transcode_to_wav",
            AsyncMock(return_value=wav_30s),
        ),
        patch.object(client, "_post_chunk_to_whisper", side_effect=_fake_post_fail_at_1),
        pytest.raises(ASRError),
    ):
        async for chunk in client.stream_transcribe(_make_audio()):
            collected.append(chunk)

    # チャンク 0 は成功したため collected に入る
    assert len(collected) == 1
    assert collected[0].chunk_index == 0


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
