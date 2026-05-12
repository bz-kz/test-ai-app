"""音声ストリーミング文字起こしユースケース (BE-017)。

音声データを受け取り ASR クライアントの stream_transcribe 経由で
TranscribeChunk を逐次 yield する。
DB への書き込みは一切行わない (SPEC.md#transcribe-streaming-endpoint: no persistence)。
interfaces 層はインポートしない (DDD 方向: usecases → infrastructure → domain)。

PHI ルール:
  - audio.audio_bytes は PHI (音声録音)。ログに書かない。
  - chunk.text (トランスクリプトチャンク) は PHI。ログには長さのみ記録する。
  - clinician_id はログには short_id で記録する。
  - 監査ログ行は書かない (SPEC.md#transcribe-streaming-endpoint 明示)。
  - ASRError はそのまま伝播させる (ルーター層で SSE error イベントに変換する)。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from uuid import UUID

from app.domain.phi import short_id
from app.infrastructure.asr.client import LocalASRClient
from app.infrastructure.asr.config import ASR_STREAM_TOTAL_TIMEOUT_S
from app.infrastructure.asr.errors import ASRError
from app.infrastructure.asr.types import AudioPayload, TranscribeChunk, TranscribeParams
from app.infrastructure.db.repositories import EncounterRepository
from app.usecases.errors import EncounterNotFound

logger = logging.getLogger(__name__)


async def stream_transcribe_audio(
    *,
    audio: AudioPayload,
    params: TranscribeParams | None = None,
    encounter_id: UUID,
    clinician_id: UUID,
    asr: LocalASRClient,
    encounter_repo: EncounterRepository,
) -> AsyncGenerator[TranscribeChunk, None]:
    """音声データをストリーミング文字起こしして TranscribeChunk を yield する。

    処理順序:
      1. 受診の存在確認 (EncounterNotFound を raise する可能性あり — ストリーム開始前)
      2. ASR クライアントの stream_transcribe を呼び出す
      3. 各チャンクを ASR_STREAM_TOTAL_TIMEOUT_S 秒のタイムアウト付きで yield する
         タイムアウト時は ASRError(timeout=True) を raise する

    PHI: audio.audio_bytes および chunk.text はログに書かない。
    clinician_id / encounter_id は short_id でのみ記録する。
    """
    return _stream_impl(
        audio=audio,
        params=params,
        encounter_id=encounter_id,
        clinician_id=clinician_id,
        asr=asr,
        encounter_repo=encounter_repo,
    )


async def _stream_impl(
    *,
    audio: AudioPayload,
    params: TranscribeParams | None,
    encounter_id: UUID,
    clinician_id: UUID,
    asr: LocalASRClient,
    encounter_repo: EncounterRepository,
) -> AsyncGenerator[TranscribeChunk, None]:
    """stream_transcribe_audio の実体 (async generator)。

    SPEC: EncounterNotFound はストリームを開く前に raise する。
    ルーターは generator.__anext__() を一度試みて EncounterNotFound をキャッチし
    HTTP 404 に変換する (BE-013 パターン)。
    """
    # (1) 受診存在確認: ストリーム開始前に同期的に確認する
    encounter = await encounter_repo.find_by_id(encounter_id)
    if encounter is None:
        logger.debug("stream_transcribe_audio aborted: encounter not found")
        raise EncounterNotFound

    logger.info(
        "stream_transcribe_audio start: encounter_id=%s clinician_id=%s",
        short_id(encounter_id),
        short_id(clinician_id),
    )

    # (2) ASR ストリーミング呼び出し: ASRError はキャッチせず伝播させる
    # audio.audio_bytes および chunk.text は PHI のためログに書かない
    # stream_transcribe は同期メソッドで AsyncIterator を返す (coroutine ではない)
    asr_stream = asr.stream_transcribe(audio, params)

    # (3) 各チャンクをエンドツーエンドタイムアウト付きで yield する
    # 次の __anext__() を asyncio.wait_for でラップしてチャンク取得ごとにタイムアウトを強制する。
    # タイムアウト時は ASRError(timeout=True) に変換する (ルーターが SSE error に変換する)。
    chunk_index = 0
    aiter = asr_stream.__aiter__()
    while True:
        try:
            chunk = await asyncio.wait_for(
                aiter.__anext__(),
                timeout=ASR_STREAM_TOTAL_TIMEOUT_S,
            )
        except StopAsyncIteration:
            break
        except TimeoutError as exc:
            raise ASRError(
                f"stream total timeout exceeded at chunk {chunk_index}",
                timeout=True,
            ) from exc
        # ASRError はキャッチせず伝播させる

        # チャンクテキストはログに書かない; 長さのみ記録する (DEBUG レベルのみ)
        logger.debug(
            "stream_transcribe_audio chunk: encounter_id=%s chunk_index=%d text_length=%d",
            short_id(encounter_id),
            chunk.chunk_index,
            len(chunk.text),
        )
        logger.info(
            "stream_transcribe_audio chunk: encounter_id=%s chunk_index=%d chunk_count=%d",
            short_id(encounter_id),
            chunk.chunk_index,
            chunk.chunk_count,
        )
        chunk_index += 1
        yield chunk

    logger.info(
        "stream_transcribe_audio done: encounter_id=%s chunk_count=%d",
        short_id(encounter_id),
        chunk_index,
    )
