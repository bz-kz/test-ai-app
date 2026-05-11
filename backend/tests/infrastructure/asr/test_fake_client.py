"""FakeLocalASRClient のユニットテスト。決定論的振る舞いと force_error を検証する。"""

from __future__ import annotations

import hashlib

import pytest

from app.infrastructure.asr.errors import ASRError
from app.infrastructure.asr.fake_client import FakeLocalASRClient
from app.infrastructure.asr.types import AudioPayload, TranscribeParams


def _make_audio(content: bytes = b"fake-audio-data") -> AudioPayload:
    return AudioPayload(audio_bytes=content, content_type="audio/webm;codecs=opus")


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
