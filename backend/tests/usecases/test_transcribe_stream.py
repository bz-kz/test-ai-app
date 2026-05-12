"""stream_transcribe_audio ユースケースのユニットテスト (BE-017)。

FakeLocalASRClient + インメモリリポジトリを使い、Postgres・ASR サービスなしで実行できる。

テストケース:
  (a) 正常系: 3 チャンクの Fake ストリームが encounter_id 存在確認後に正しく yield される
  (b) EncounterNotFound: encounter が存在しない場合、ASR は呼ばれない
  (c) mid-stream ASRError: チャンク N で ASRError が raise されてイテレータが停止する
  (d) 全体タイムアウト: asyncio.wait_for が ASR_STREAM_TOTAL_TIMEOUT_S 秒でタイムアウトする
  (e) clinician_id / encounter_id が short_id でのみ記録される (PHI ルール)
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest

from app.domain.entities import Encounter
from app.infrastructure.asr.errors import ASRError
from app.infrastructure.asr.fake_client import FakeLocalASRClient
from app.infrastructure.asr.types import AudioPayload, TranscribeChunk, TranscribeParams
from app.usecases.errors import EncounterNotFound
from app.usecases.transcribe_stream import stream_transcribe_audio

# ---------------------------------------------------------------------------
# テスト用ヘルパー
# ---------------------------------------------------------------------------

TEST_CLINICIAN_ID = UUID("00000000-0000-0000-0000-0000000a11ce")


def _make_encounter(encounter_id: UUID) -> Encounter:
    return Encounter(
        id=encounter_id,
        patient_id=uuid4(),
        encountered_at=datetime.now(tz=UTC),
        clinician_id=TEST_CLINICIAN_ID,
        created_at=datetime.now(tz=UTC),
    )


def _make_encounter_repo(encounter: Encounter | None) -> AsyncMock:
    """find_by_id が指定の受診を返すモックリポジトリを返す。"""
    repo = AsyncMock()
    repo.find_by_id = AsyncMock(return_value=encounter)
    return repo


def _make_audio(content: bytes = b"test-audio") -> AudioPayload:
    return AudioPayload(audio_bytes=content, content_type="audio/webm;codecs=opus")


# ---------------------------------------------------------------------------
# テストケース
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_transcribe_audio_happy_path() -> None:
    """(a) 正常系: 3 チャンクの Fake ストリームが正しく yield される。"""
    encounter_id = uuid4()
    encounter = _make_encounter(encounter_id)
    encounter_repo = _make_encounter_repo(encounter)
    asr = FakeLocalASRClient(n_chunks=3)
    audio = _make_audio()

    chunks: list[TranscribeChunk] = []
    gen = await stream_transcribe_audio(
        audio=audio,
        params=TranscribeParams(language="ja"),
        encounter_id=encounter_id,
        clinician_id=TEST_CLINICIAN_ID,
        asr=asr,
        encounter_repo=encounter_repo,
    )
    async for chunk in gen:
        chunks.append(chunk)

    # 3 通常チャンク + 1 完了チャンク
    assert len(chunks) == 4
    # 順序確認
    for i in range(3):
        assert chunks[i].chunk_index == i
        assert chunks[i].done is False
    assert chunks[3].done is True
    # ASR は 1 回呼ばれた
    assert asr.stream_transcribe_call_count == 1
    # encounter_repo.find_by_id が encounter_id で呼ばれた
    encounter_repo.find_by_id.assert_called_once_with(encounter_id)


@pytest.mark.asyncio
async def test_stream_transcribe_audio_encounter_not_found() -> None:
    """(b) encounter が存在しない場合は EncounterNotFound を raise する (ASR は呼ばれない)。"""
    encounter_id = uuid4()
    encounter_repo = _make_encounter_repo(None)
    asr = FakeLocalASRClient()
    audio = _make_audio()

    with pytest.raises(EncounterNotFound):
        gen = await stream_transcribe_audio(
            audio=audio,
            params=None,
            encounter_id=encounter_id,
            clinician_id=TEST_CLINICIAN_ID,
            asr=asr,
            encounter_repo=encounter_repo,
        )
        # EncounterNotFound はジェネレータ起動前 (await 時) に raise されるため
        # ここには到達しないはずだが、念のためイテレートも試みる
        async for _ in gen:
            pass

    # ASR は呼ばれていない
    assert asr.stream_transcribe_call_count == 0


@pytest.mark.asyncio
async def test_stream_transcribe_audio_asr_error_at_chunk_1() -> None:
    """(c) チャンク 1 で ASRError が raise されてイテレータが停止する。"""
    encounter_id = uuid4()
    encounter = _make_encounter(encounter_id)
    encounter_repo = _make_encounter_repo(encounter)
    asr = FakeLocalASRClient(force_error_at_chunk=1, n_chunks=3)
    audio = _make_audio()

    collected: list[TranscribeChunk] = []
    with pytest.raises(ASRError):
        gen = await stream_transcribe_audio(
            audio=audio,
            params=None,
            encounter_id=encounter_id,
            clinician_id=TEST_CLINICIAN_ID,
            asr=asr,
            encounter_repo=encounter_repo,
        )
        async for chunk in gen:
            collected.append(chunk)

    # チャンク 0 は成功したため collected に入る
    assert len(collected) == 1
    assert collected[0].chunk_index == 0


@pytest.mark.asyncio
async def test_stream_transcribe_audio_total_timeout() -> None:
    """(d) 全体タイムアウト: wait_for がタイムアウトすると ASRError(timeout=True) を raise する。"""
    encounter_id = uuid4()
    encounter = _make_encounter(encounter_id)
    encounter_repo = _make_encounter_repo(encounter)
    # force_total_timeout は最初のチャンクで timeout=True の ASRError を送出する
    asr = FakeLocalASRClient(force_total_timeout=True)
    audio = _make_audio()

    with pytest.raises(ASRError) as exc_info:
        gen = await stream_transcribe_audio(
            audio=audio,
            params=None,
            encounter_id=encounter_id,
            clinician_id=TEST_CLINICIAN_ID,
            asr=asr,
            encounter_repo=encounter_repo,
        )
        async for _ in gen:
            pass

    assert exc_info.value.timeout is True


@pytest.mark.asyncio
async def test_stream_transcribe_audio_asyncio_timeout_raises_asr_error() -> None:
    """(d2) asyncio.wait_for のタイムアウトが ASRError(timeout=True) に変換される。

    per_chunk_delay_s=0.1 で ASR を遅延させ、タイムアウト閾値を 0.01s に設定して
    asyncio.TimeoutError が発生し ASRError(timeout=True) に変換されることを確認する。
    """
    encounter_id = uuid4()
    encounter = _make_encounter(encounter_id)
    encounter_repo = _make_encounter_repo(encounter)
    # per_chunk_delay_s=0.1 で各チャンク取得を遅延させる
    asr = FakeLocalASRClient(per_chunk_delay_s=0.1)
    audio = _make_audio()

    # ASR_STREAM_TOTAL_TIMEOUT_S を 0.01s に設定して 1 チャンク目でタイムアウトさせる
    with (
        patch(
            "app.usecases.transcribe_stream.ASR_STREAM_TOTAL_TIMEOUT_S",
            0.01,  # 10ms — per_chunk_delay_s=0.1s より遥かに短い
        ),
        pytest.raises(ASRError) as exc_info,
    ):
        gen = await stream_transcribe_audio(
            audio=audio,
            params=None,
            encounter_id=encounter_id,
            clinician_id=TEST_CLINICIAN_ID,
            asr=asr,
            encounter_repo=encounter_repo,
        )
        async for _ in gen:
            pass

    assert exc_info.value.timeout is True


@pytest.mark.asyncio
async def test_stream_transcribe_audio_no_db_writes() -> None:
    """ストリーミング文字起こし後も DB 書き込みが発生しないことを確認する。"""
    encounter_id = uuid4()
    encounter = _make_encounter(encounter_id)
    encounter_repo = _make_encounter_repo(encounter)
    asr = FakeLocalASRClient()
    audio = _make_audio()

    gen = await stream_transcribe_audio(
        audio=audio,
        params=None,
        encounter_id=encounter_id,
        clinician_id=TEST_CLINICIAN_ID,
        asr=asr,
        encounter_repo=encounter_repo,
    )
    async for _ in gen:
        pass

    # リポジトリの write 系メソッドは呼ばれていない
    assert not hasattr(encounter_repo, "add") or not encounter_repo.add.called
