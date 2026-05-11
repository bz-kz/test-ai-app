"""transcribe_audio ユースケースのユニットテスト。

FakeLocalASRClient + インメモリリポジトリを使い、Postgres・ASR サービスなしで実行できる。
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from app.domain.entities import Encounter
from app.infrastructure.asr.errors import ASRError
from app.infrastructure.asr.fake_client import FakeLocalASRClient
from app.infrastructure.asr.types import AudioPayload, TranscribeParams
from app.usecases.errors import EncounterNotFound
from app.usecases.transcribe import transcribe_audio

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
async def test_transcribe_audio_happy_path() -> None:
    """正常系: 受診が存在し ASR が成功する場合にトランスクリプトを返す。"""
    encounter_id = uuid4()
    encounter = _make_encounter(encounter_id)
    encounter_repo = _make_encounter_repo(encounter)
    asr = FakeLocalASRClient()
    audio = _make_audio()

    result = await transcribe_audio(
        audio=audio,
        params=TranscribeParams(language="ja"),
        encounter_id=encounter_id,
        clinician_id=TEST_CLINICIAN_ID,
        asr=asr,
        encounter_repo=encounter_repo,
    )

    assert result.text == FakeLocalASRClient.DEFAULT_TRANSCRIPT
    assert asr.transcribe_call_count == 1
    # DB 書き込みなし: リポジトリの add/save 系メソッドは呼ばれていない
    encounter_repo.find_by_id.assert_called_once_with(encounter_id)


@pytest.mark.asyncio
async def test_transcribe_audio_encounter_not_found() -> None:
    """受診が存在しない場合は EncounterNotFound を raise する (ASR は呼ばれない)。"""
    encounter_id = uuid4()
    encounter_repo = _make_encounter_repo(None)
    asr = FakeLocalASRClient()
    audio = _make_audio()

    with pytest.raises(EncounterNotFound):
        await transcribe_audio(
            audio=audio,
            params=None,
            encounter_id=encounter_id,
            clinician_id=TEST_CLINICIAN_ID,
            asr=asr,
            encounter_repo=encounter_repo,
        )

    # ASR は呼ばれていない
    assert asr.transcribe_call_count == 0


@pytest.mark.asyncio
async def test_transcribe_audio_asr_error_propagates() -> None:
    """ASR クライアントが ASRError を送出した場合、そのまま伝播する。"""
    encounter_id = uuid4()
    encounter = _make_encounter(encounter_id)
    encounter_repo = _make_encounter_repo(encounter)
    asr = FakeLocalASRClient(force_error=True)
    audio = _make_audio()

    with pytest.raises(ASRError):
        await transcribe_audio(
            audio=audio,
            params=None,
            encounter_id=encounter_id,
            clinician_id=TEST_CLINICIAN_ID,
            asr=asr,
            encounter_repo=encounter_repo,
        )

    assert asr.transcribe_call_count == 1


@pytest.mark.asyncio
async def test_transcribe_audio_timeout_propagates() -> None:
    """ASR がタイムアウトの ASRError を送出した場合、timeout=True のまま伝播する。"""
    encounter_id = uuid4()
    encounter = _make_encounter(encounter_id)
    encounter_repo = _make_encounter_repo(encounter)
    asr = FakeLocalASRClient(force_timeout=True)
    audio = _make_audio()

    with pytest.raises(ASRError) as exc_info:
        await transcribe_audio(
            audio=audio,
            params=None,
            encounter_id=encounter_id,
            clinician_id=TEST_CLINICIAN_ID,
            asr=asr,
            encounter_repo=encounter_repo,
        )

    assert exc_info.value.timeout is True


@pytest.mark.asyncio
async def test_transcribe_audio_no_params() -> None:
    """params=None の場合も正常に動作する。"""
    encounter_id = uuid4()
    encounter = _make_encounter(encounter_id)
    encounter_repo = _make_encounter_repo(encounter)
    asr = FakeLocalASRClient()
    audio = _make_audio()

    result = await transcribe_audio(
        audio=audio,
        params=None,
        encounter_id=encounter_id,
        clinician_id=TEST_CLINICIAN_ID,
        asr=asr,
        encounter_repo=encounter_repo,
    )

    assert result.text == FakeLocalASRClient.DEFAULT_TRANSCRIPT
