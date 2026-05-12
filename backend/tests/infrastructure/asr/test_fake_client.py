"""FakeLocalASRClient のユニットテスト。決定論的振る舞いと force_error を検証する。

BE-014: transcribe / ping のテスト
BE-017: stream_transcribe のテスト (チャンク数・エラー注入・delay)
"""

from __future__ import annotations

import hashlib

import pytest

from app.infrastructure.asr.errors import ASRError
from app.infrastructure.asr.fake_client import FakeLocalASRClient
from app.infrastructure.asr.types import AudioPayload, TranscribeChunk, TranscribeParams


def _make_audio(content: bytes = b"fake-audio-data") -> AudioPayload:
    return AudioPayload(audio_bytes=content, content_type="audio/webm;codecs=opus")


# ---------------------------------------------------------------------------
# transcribe テスト (BE-014)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fake_transcribe_default_response() -> None:
    """フィクスチャに未登録の音声はデフォルトトランスクリプトを返す。"""
    client = FakeLocalASRClient()
    result = await client.transcribe(_make_audio())
    assert result.text == FakeLocalASRClient.DEFAULT_TRANSCRIPT
    assert client.transcribe_call_count == 1


@pytest.mark.asyncio
async def test_fake_transcribe_fixture_map() -> None:
    """フィクスチャマップに登録済みの音声は対応するトランスクリプトを返す。"""
    audio = b"specific-audio"
    key = hashlib.sha256(audio).hexdigest()[:16]
    client = FakeLocalASRClient(fixture_map={key: "患者は元気です。"})
    result = await client.transcribe(_make_audio(audio))
    assert result.text == "患者は元気です。"


@pytest.mark.asyncio
async def test_fake_transcribe_force_error() -> None:
    """force_error=True のとき ASRError を送出する。"""
    client = FakeLocalASRClient(force_error=True)
    with pytest.raises(ASRError) as exc_info:
        await client.transcribe(_make_audio())
    # 音声バイト列が例外文字列に含まれないことを確認
    assert b"fake-audio-data" not in str(exc_info.value).encode()
    assert exc_info.value.timeout is False


@pytest.mark.asyncio
async def test_fake_transcribe_force_timeout() -> None:
    """force_timeout=True のとき timeout=True の ASRError を送出する。"""
    client = FakeLocalASRClient(force_timeout=True)
    with pytest.raises(ASRError) as exc_info:
        await client.transcribe(_make_audio())
    assert exc_info.value.timeout is True


@pytest.mark.asyncio
async def test_fake_transcribe_with_params() -> None:
    """TranscribeParams を渡しても正常に動作することを確認する。"""
    client = FakeLocalASRClient()
    params = TranscribeParams(language="ja")
    result = await client.transcribe(_make_audio(), params)
    assert result.text == FakeLocalASRClient.DEFAULT_TRANSCRIPT


@pytest.mark.asyncio
async def test_fake_ping_true() -> None:
    client = FakeLocalASRClient(ping_result=True)
    result = await client.ping()
    assert result is True
    assert client.ping_call_count == 1


@pytest.mark.asyncio
async def test_fake_ping_false() -> None:
    client = FakeLocalASRClient(ping_result=False)
    result = await client.ping()
    assert result is False
    assert client.ping_call_count == 1


@pytest.mark.asyncio
async def test_fake_no_duration_in_response() -> None:
    """デフォルト応答の duration_seconds は None。"""
    client = FakeLocalASRClient()
    result = await client.transcribe(_make_audio())
    assert result.duration_seconds is None


# ---------------------------------------------------------------------------
# stream_transcribe テスト (BE-017)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fake_stream_transcribe_default_3_chunks() -> None:
    """デフォルト設定で 3 通常チャンク + 1 完了チャンク (計 4) を yield する。"""
    client = FakeLocalASRClient()
    chunks: list[TranscribeChunk] = []
    async for chunk in client.stream_transcribe(_make_audio()):
        chunks.append(chunk)

    # 3 通常 + 1 完了
    assert len(chunks) == 4
    # 最初の 3 チャンクは done=False
    for i in range(3):
        assert chunks[i].done is False
        assert chunks[i].chunk_index == i
        assert chunks[i].chunk_count == 3
    # 最後は done=True
    assert chunks[3].done is True
    assert chunks[3].chunk_count == 3
    # 呼び出しカウントが記録される
    assert client.stream_transcribe_call_count == 1


@pytest.mark.asyncio
async def test_fake_stream_transcribe_full_text_in_done_chunk() -> None:
    """完了チャンクの text は全チャンクのテキストを結合したものになる。"""
    client = FakeLocalASRClient(n_chunks=3)
    chunks: list[TranscribeChunk] = []
    async for chunk in client.stream_transcribe(_make_audio()):
        chunks.append(chunk)

    done_chunk = chunks[-1]
    assert done_chunk.done is True
    # 全チャンクのテキストを結合したものが full_text に入っている
    partial_texts = [c.text for c in chunks[:-1]]
    assert done_chunk.text == "".join(partial_texts)


@pytest.mark.asyncio
async def test_fake_stream_transcribe_force_error_at_chunk_1() -> None:
    """force_error_at_chunk=1 のとき、チャンク 1 で ASRError を送出してイテレータを停止する。"""
    client = FakeLocalASRClient(force_error_at_chunk=1)
    collected: list[TranscribeChunk] = []

    with pytest.raises(ASRError):
        async for chunk in client.stream_transcribe(_make_audio()):
            collected.append(chunk)

    # チャンク 0 は成功したため collected に入る
    assert len(collected) == 1
    assert collected[0].chunk_index == 0


@pytest.mark.asyncio
async def test_fake_stream_transcribe_force_error_at_chunk_0() -> None:
    """force_error_at_chunk=0 のとき、最初のチャンクで ASRError を送出する。"""
    client = FakeLocalASRClient(force_error_at_chunk=0)
    collected: list[TranscribeChunk] = []

    with pytest.raises(ASRError):
        async for chunk in client.stream_transcribe(_make_audio()):
            collected.append(chunk)

    assert len(collected) == 0


@pytest.mark.asyncio
async def test_fake_stream_transcribe_force_total_timeout() -> None:
    """force_total_timeout=True のとき timeout=True の ASRError を送出する。"""
    client = FakeLocalASRClient(force_total_timeout=True)

    with pytest.raises(ASRError) as exc_info:
        async for _ in client.stream_transcribe(_make_audio()):
            pass

    assert exc_info.value.timeout is True


@pytest.mark.asyncio
async def test_fake_stream_transcribe_custom_n_chunks() -> None:
    """n_chunks=5 のとき 5 通常チャンク + 1 完了チャンク (計 6) を yield する。"""
    client = FakeLocalASRClient(n_chunks=5)
    chunks: list[TranscribeChunk] = []
    async for chunk in client.stream_transcribe(_make_audio()):
        chunks.append(chunk)

    assert len(chunks) == 6
    assert chunks[-1].done is True
    assert chunks[-1].chunk_count == 5


@pytest.mark.asyncio
async def test_fake_stream_transcribe_no_phi_in_error() -> None:
    """ASRError が音声バイト列を含まないことを確認する (PHI ルール)。"""
    client = FakeLocalASRClient(force_error_at_chunk=0)
    sensitive_audio = b"patient-voice-recording-phi"

    with pytest.raises(ASRError) as exc_info:
        async for _ in client.stream_transcribe(_make_audio(sensitive_audio)):
            pass

    assert b"patient-voice-recording-phi" not in str(exc_info.value).encode()
