"""音声文字起こしユースケース。

音声データを受け取り ASR クライアント経由でトランスクリプトを返す。
DB への書き込みは一切行わない (SPEC.md#transcribe-endpoint: no persistence)。
interfaces 層はインポートしない (DDD 方向: usecases → infrastructure → domain)。

PHI ルール:
  - audio.audio_bytes は PHI (音声録音)。ログに書かない。
  - text (トランスクリプト) は PHI。ログには長さのみ記録する。
  - clinician_id はログには short_id で記録する。
  - 監査ログ行は書かない (SPEC.md#transcribe-endpoint 明示)。
  - ASRError はそのまま伝播させる (ルーター層で 503/504 に変換する)。
"""

from __future__ import annotations

import logging
from uuid import UUID

from app.domain.phi import short_id
from app.infrastructure.asr.client import LocalASRClient
from app.infrastructure.asr.types import AudioPayload, TranscribeParams, TranscribeResponse
from app.infrastructure.db.repositories import EncounterRepository
from app.usecases.errors import EncounterNotFound

logger = logging.getLogger(__name__)


async def transcribe_audio(
    *,
    audio: AudioPayload,
    params: TranscribeParams | None = None,
    encounter_id: UUID,
    clinician_id: UUID,
    asr: LocalASRClient,
    encounter_repo: EncounterRepository,
) -> TranscribeResponse:
    """音声データを文字起こしして TranscribeResponse を返す。

    処理順序:
      1. 受診の存在確認 (EncounterNotFound を raise する可能性あり)
      2. ASR クライアントで文字起こし (ASRError を raise する可能性あり)
      3. トランスクリプトを返す (DB 書き込みなし・監査ログなし)

    PHI: audio.audio_bytes および result.text はログに書かない。
    clinician_id は short_id でのみ記録する。
    """
    # (1) 受診存在確認
    encounter = await encounter_repo.find_by_id(encounter_id)
    if encounter is None:
        logger.debug("transcribe_audio aborted: encounter not found")
        raise EncounterNotFound

    logger.info(
        "transcribe_audio start: encounter_id=%s clinician_id=%s",
        short_id(encounter_id),
        short_id(clinician_id),
    )

    # (2) ASR 呼び出し: ASRError はキャッチせず伝播させる
    # audio.audio_bytes および result.text は PHI のためログに書かない
    result = await asr.transcribe(audio, params)

    # トランスクリプト本文はログに書かない; 長さのみ記録する
    logger.info(
        "transcribe_audio done: encounter_id=%s text_length=%d",
        short_id(encounter_id),
        len(result.text),
    )

    return result
