"""音声文字起こしエンドポイントルーター (BE-014 / BE-017)。

POST /encounters/{encounter_id}/transcribe        — multipart 音声アップロード → トランスクリプト
POST /encounters/{encounter_id}/transcribe/stream — SSE ストリーミング文字起こし


PHI ルール:
  - audio_bytes はリクエスト受信後すぐ ASR クライアントに渡し、保持しない。
  - ファイル名 (multipart filename) はルーター境界で捨てる — ログ・DB に書かない。
  - トランスクリプト本文は DEBUG のみ mask_phi を通して記録する。
  - エラーメッセージに UUID・音声内容・トランスクリプト本文を含めない。
  - ASRError は 503/504 に変換する (InferenceError → 503 と同方針)。
  - SSE error フレームには code と chunk_index のみ含める — masked_context は含めない。

レイヤー方向:
  interfaces → usecases のみ。infrastructure は直接参照しない。
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.domain.phi import mask_phi, short_id
from app.interfaces.auth import get_current_clinician
from app.interfaces.schemas import ErrorResponse
from app.usecases.di import (
    AudioPayload,
    StreamTranscribeAudioCallable,
    TranscribeAudioCallable,
    TranscribeParams,
    make_stream_transcribe_audio,
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
# 共通バリデーションヘルパー
# ---------------------------------------------------------------------------


async def _validate_audio(audio: UploadFile) -> tuple[str, bytes]:
    """コンテンツタイプとサイズを検証し (content_type, audio_bytes) を返す。

    検証失敗時は HTTPException (415 または 422) を送出する。
    ファイル名はここで捨てる — PHI ルール §3。
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

    return ct, audio_bytes


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
    ct, audio_bytes = await _validate_audio(audio)

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


@router.post(
    "/encounters/{encounter_id}/transcribe/stream",
    response_class=StreamingResponse,
    status_code=200,
    responses={
        401: {"model": ErrorResponse, "description": "X-Clinician-Id ヘッダーが欠落または不正"},
        404: {"model": ErrorResponse, "description": "受診が見つからない (同期エラー)"},
        415: {"model": ErrorResponse, "description": "サポートされていないメディアタイプ"},
        422: {"model": ErrorResponse, "description": "ペイロード過大またはバリデーションエラー"},
    },
    summary="音声文字起こし (SSE ストリーミング)",
)
async def post_transcribe_stream(
    encounter_id: UUID,
    audio: UploadFile = File(..., description="WebM/Opus コンテナの音声ファイル"),
    clinician_id: UUID = Depends(get_current_clinician),
    stream_transcribe: StreamTranscribeAudioCallable = Depends(make_stream_transcribe_audio),
) -> StreamingResponse:
    """multipart 音声ファイルを受け取り SSE でチャンクごとの文字起こしを返す (BE-017)。

    SSE イベント形式 (BE-013 エンベロープと同一):
      - 通常チャンク:   data: {"text": "...", "chunk_index": N, "done": false}\\n\\n
      - 完了チャンク:   event: complete\\ndata: {"full_text": "...", "chunk_count": M}\\n\\n
      - エラーチャンク: event: error\\ndata: {"code": "...", "chunk_index": N}\\n\\n

    encounter_id が存在しない場合は 404 を返す (ストリームを開く前の同期エラー)。
    mid-stream エラーは SSE error イベントとして送出してストリームを閉じる。
    SSE error フレームには code と chunk_index のみ含める — PHI は含めない。
    ファイル名はルーター境界で捨てる (PHI ルール §3)。
    """
    # (1) バリデーション (同期的、ストリーム開始前)
    ct, audio_bytes = await _validate_audio(audio)

    # ファイル名はここで捨てる — ログにも DB にも書かない
    payload = AudioPayload(audio_bytes=audio_bytes, content_type=ct)
    params = TranscribeParams(language="ja")

    # (2) ユースケースジェネレータを取得する
    # EncounterNotFound はジェネレータの最初の yield 前に raise されるため
    # __anext__() を一度試みて同期的に 404 に変換する (BE-013 パターン)
    gen = stream_transcribe(payload, params, encounter_id, clinician_id)

    _asr_error_before_stream: ASRError | None = None
    first_chunk = None
    try:
        first_chunk = await gen.__anext__()
    except EncounterNotFound:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "encounter_not_found",
                "message": "Encounter not found.",
            },
        ) from None
    except ASRError as exc:
        # 最初のチャンク取得時に ASRError が来た場合は SSE error ストリームを返す
        _asr_error_before_stream = exc
        logger.warning(
            "ASR error at stream start: encounter_id=%s %s",
            short_id(encounter_id),
            exc.masked_context,
        )
    except StopAsyncIteration:
        first_chunk = None

    logger.info(
        "post_transcribe_stream: encounter_id=%s clinician_id=%s streaming_started=True",
        short_id(encounter_id),
        short_id(clinician_id),
    )

    # (3) SSE ジェネレータ本体
    async def _sse_generator() -> AsyncGenerator[bytes, None]:
        # 最初のチャンク取得前に ASRError が来た場合は error イベントだけ送出する
        if _asr_error_before_stream is not None:
            _exc = _asr_error_before_stream
            code = "transcription_timeout" if _exc.timeout else "transcription_unavailable"
            error_payload = json.dumps(
                # SSE error フレームには code と chunk_index のみ — PHI は含めない
                {"code": code, "chunk_index": 0},
                ensure_ascii=False,
            )
            yield f"event: error\ndata: {error_payload}\n\n".encode()
            return

        # 先読みしたチャンクがない場合はストリームをスキップ
        if first_chunk is None:
            return

        current = first_chunk
        last_chunk_index = 0

        while True:
            if current.done:
                # done=True は完了チャンク: full_text を completion イベントとして送出する
                completion_payload = json.dumps(
                    {
                        "full_text": current.text,
                        "duration_seconds": None,
                        "chunk_count": current.chunk_count,
                    },
                    ensure_ascii=False,
                )
                yield f"event: complete\ndata: {completion_payload}\n\n".encode()
                break
            else:
                # 通常チャンク: chunk_text は PHI だが呼び出し元が明示的に要求したため返却する
                # (local-llm-and-phi.md §4 操作的読み取り)
                chunk_payload = json.dumps(
                    {
                        "text": current.text,
                        "chunk_index": current.chunk_index,
                        "chunk_count": current.chunk_count,
                        "done": False,
                    },
                    ensure_ascii=False,
                )
                yield f"data: {chunk_payload}\n\n".encode()
                last_chunk_index = current.chunk_index

                # チャンクテキストは DEBUG のみ mask_phi 経由で記録する
                logger.debug(
                    "SSE chunk: encounter_id=%s chunk_index=%d text=%s",
                    short_id(encounter_id),
                    current.chunk_index,
                    mask_phi(current.text),
                )
                logger.info(
                    "SSE chunk: encounter_id=%s chunk_index=%d chunk_count=%d",
                    short_id(encounter_id),
                    current.chunk_index,
                    current.chunk_count,
                )

            # 次のチャンクを取得する
            try:
                current = await gen.__anext__()
            except StopAsyncIteration:
                break
            except ASRError as exc:
                # mid-stream ASRError: SSE error イベントとして送出してストリームを閉じる
                # SSE error フレームには code と chunk_index のみ含める — PHI は含めない
                logger.warning(
                    "ASR error mid-stream: encounter_id=%s chunk_index=%d %s",
                    short_id(encounter_id),
                    last_chunk_index + 1,
                    exc.masked_context,
                )
                code = "transcription_timeout" if exc.timeout else "transcription_unavailable"
                error_payload = json.dumps(
                    {"code": code, "chunk_index": last_chunk_index + 1},
                    ensure_ascii=False,
                )
                yield f"event: error\ndata: {error_payload}\n\n".encode()
                break

    return StreamingResponse(
        _sse_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
