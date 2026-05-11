"""音声文字起こしエンドポイントルーター (BE-014)。

POST /encounters/{encounter_id}/transcribe — multipart 音声アップロード → 日本語トランスクリプト

PHI ルール:
  - audio_bytes はリクエスト受信後すぐ ASR クライアントに渡し、保持しない。
  - ファイル名 (multipart filename) はルーター境界で捨てる — ログ・DB に書かない。
  - トランスクリプト本文は DEBUG のみ mask_phi を通して記録する。
  - エラーメッセージに UUID・音声内容・トランスクリプト本文を含めない。
  - ASRError は 503/504 に変換する (InferenceError → 503 と同方針)。

レイヤー方向:
  interfaces → usecases のみ。infrastructure は直接参照しない。
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.domain.phi import mask_phi, short_id
from app.interfaces.auth import get_current_clinician
from app.interfaces.schemas import ErrorResponse
from app.usecases.di import (
    AudioPayload,
    TranscribeAudioCallable,
    TranscribeParams,
    make_transcribe_audio,
)
from app.usecases.errors import ASRError, EncounterNotFound

logger = logging.getLogger(__name__)

router = APIRouter(tags=["transcribe"])

# ペイロードの最大サイズ: 2 MB
_MAX_AUDIO_BYTES = 2 * 1024 * 1024

# 受け付けるコンテンツタイプ
_ALLOWED_CONTENT_TYPES = {"audio/webm", "audio/webm;codecs=opus"}


# ---------------------------------------------------------------------------
# Pydantic モデル
# ---------------------------------------------------------------------------


class TranscribeRead(BaseModel):
    """文字起こしレスポンス。

    text は PHI だが、呼び出し元が明示的に transcribe エンドポイントを叩いたため返却する
    (local-llm-and-phi.md §4 操作的読み取り)。
    """

    text: str
    encounter_id: UUID
    duration_seconds: float | None


# ---------------------------------------------------------------------------
# エンドポイント
# ---------------------------------------------------------------------------


@router.post(
    "/encounters/{encounter_id}/transcribe",
    response_model=TranscribeRead,
    status_code=200,
    responses={
        401: {"model": ErrorResponse, "description": "X-Clinician-Id ヘッダーが欠落または不正"},
        404: {"model": ErrorResponse, "description": "受診が見つからない"},
        415: {"model": ErrorResponse, "description": "サポートされていないメディアタイプ"},
        422: {"model": ErrorResponse, "description": "ペイロード過大またはバリデーションエラー"},
        503: {"model": ErrorResponse, "description": "ASR サービス一時利用不可"},
        504: {"model": ErrorResponse, "description": "ASR タイムアウト"},
    },
    summary="音声文字起こし",
)
async def post_transcribe(
    encounter_id: UUID,
    audio: UploadFile = File(..., description="WebM/Opus コンテナの音声ファイル"),
    clinician_id: UUID = Depends(get_current_clinician),
    transcribe: TranscribeAudioCallable = Depends(make_transcribe_audio),
) -> TranscribeRead:
    """multipart 音声ファイルを受け取り日本語トランスクリプトを返す。

    ファイル名はルーター境界で捨てる (PHI ルール §3)。
    音声バイト列はリクエスト後すぐに解放される (DB・ディスクに書かない)。
    encounter_id が存在しない場合は 404 を返す。
    ASR が利用できない場合は 503、タイムアウトは 504 を返す。
    エラーメッセージに UUID・音声内容は含めない。
    """
    # (1) コンテンツタイプ検証
    ct = (audio.content_type or "").lower().strip()
    if ct not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail={
                "code": "unsupported_media_type",
                "message": "音声ファイルは audio/webm;codecs=opus 形式でアップロードしてください。",
            },
        )

    # (2) 音声データ読み込み + サイズ検証
    # SpooledTemporaryFile はメモリ内で保持; read() 後すぐ解放される
    audio_bytes = await audio.read()
    if len(audio_bytes) > _MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "audio_too_large",
                "message": "音声ファイルは 2 MB 以下にしてください。",
            },
        )

    # ファイル名はここで捨てる — ログにも DB にも書かない
    payload = AudioPayload(audio_bytes=audio_bytes, content_type=ct)
    params = TranscribeParams(language="ja")

    # (3) ユースケース呼び出し
    try:
        result = await transcribe(payload, params, encounter_id, clinician_id)
    except EncounterNotFound:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "encounter_not_found",
                "message": "Encounter not found.",
            },
        ) from None
    except ASRError as exc:
        if exc.timeout:
            logger.warning(
                "ASR timeout: encounter_id=%s %s",
                short_id(encounter_id),
                exc.masked_context,
            )
            raise HTTPException(
                status_code=504,
                detail={
                    "code": "transcription_timeout",
                    "message": "音声の文字起こしがタイムアウトしました。",
                },
            ) from None
        logger.warning(
            "ASR error: encounter_id=%s %s",
            short_id(encounter_id),
            exc.masked_context,
        )
        raise HTTPException(
            status_code=503,
            detail={
                "code": "transcription_unavailable",
                "message": "音声の文字起こしに失敗しました。",
            },
        ) from None

    # (4) レスポンス構築 — トランスクリプト本文は DEBUG のみ mask_phi 経由で記録
    logger.debug(
        "transcribe response: encounter_id=%s text=%s",
        short_id(encounter_id),
        mask_phi(result.text),
    )

    return TranscribeRead(
        text=result.text,
        encounter_id=encounter_id,
        duration_seconds=result.duration_seconds,
    )
