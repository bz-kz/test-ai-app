"""カルテ下書きエンドポイントルーター。

POST /encounters/{encounter_id}/drafts        — AI 生成下書きの作成
POST /encounters/{encounter_id}/drafts/stream — AI 生成下書きの SSE ストリーミング
GET  /drafts/{draft_id}                       — UUID による下書き取得
PATCH /drafts/{draft_id}                      — 臨床医による下書き編集
POST /drafts/{draft_id}/finalize              — 下書きを確定カルテに昇格

PHI ルール:
  - clinical_input および draft.content は PHI (自由記述の臨床叙述)。
  - エラーメッセージには UUID・臨床入力・下書き内容を一切含めない。
  - レスポンスの content フィールドは PHI だが、呼び出し元が明示的に下書きを要求したため
    返却が許可される (local-llm-and-phi.md §4 操作的読み取り)。
  - InferenceError は ストリームパスでは SSE error イベントに変換する (非ストリームは 503)。

レイヤー方向:
  interfaces → usecases のみ。infrastructure は直接参照しない。
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from app.domain.entities import RecordDraft
from app.domain.phi import short_id
from app.interfaces.auth import get_current_clinician
from app.interfaces.routers.finals import FinalRead
from app.interfaces.schemas import ErrorResponse
from app.interfaces.sse import sse_data_frame, sse_event_frame
from app.usecases.di import (
    EditRecordDraftCallable,
    FinalizeDraftCallable,
    FindDraftByIdCallable,
    GenerateRecordDraftCallable,
    StreamRecordDraftCallable,
    make_edit_record_draft,
    make_finalize_draft_to_record_final,
    make_find_draft_by_id,
    make_generate_record_draft,
    make_stream_record_draft,
)
from app.usecases.errors import (
    DraftNotFound,
    EncounterAlreadyFinalized,
    EncounterNotFound,
    InferenceError,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["drafts"])


# ---------------------------------------------------------------------------
# Pydantic モデル
# ---------------------------------------------------------------------------


class DraftCreate(BaseModel):
    """下書き生成リクエストボディ。

    clinical_input は PHI を含む臨床叙述。空文字列は不可。
    """

    model_config = ConfigDict(extra="forbid")

    clinical_input: str = Field(..., min_length=1)


class DraftRead(BaseModel):
    """下書きレスポンス。

    content は PHI だが、呼び出し元が明示的にこのエンドポイントを叩いたため返却する
    (local-llm-and-phi.md §4 操作的読み取り)。
    """

    id: UUID
    encounter_id: UUID
    content: str
    confidence: float | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_entity(cls, draft: RecordDraft) -> DraftRead:
        """ドメインエンティティから API レスポンスを構築する。"""
        return cls(
            id=draft.id,
            encounter_id=draft.encounter_id,
            content=draft.content,
            confidence=draft.confidence,
            created_at=draft.created_at,
            updated_at=draft.updated_at,
        )


class DraftEdit(BaseModel):
    """下書き編集リクエストボディ。

    content は PHI を含む臨床叙述。空文字列は不可。
    clinician_id は X-Clinician-Id ヘッダーから注入するためボディに含めない。
    """

    model_config = ConfigDict(extra="forbid")

    content: str = Field(..., min_length=1)


class FinalizeRequest(BaseModel):
    """下書き確定リクエストボディ。

    clinician_id は X-Clinician-Id ヘッダーから注入するためボディに含めない。
    """

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# エンドポイント
# ---------------------------------------------------------------------------


@router.post(
    "/encounters/{encounter_id}/drafts",
    response_model=DraftRead,
    status_code=201,
    responses={
        401: {"model": ErrorResponse, "description": "X-Clinician-Id ヘッダーが欠落または不正"},
        404: {"model": ErrorResponse, "description": "受診が見つからない"},
        503: {"model": ErrorResponse, "description": "推論サービス一時利用不可"},
    },
    summary="カルテ下書き生成",
)
async def post_draft(
    encounter_id: UUID,
    body: DraftCreate,
    clinician_id: UUID = Depends(get_current_clinician),
    generate: GenerateRecordDraftCallable = Depends(make_generate_record_draft),
) -> DraftRead:
    """AI によるカルテ下書きを生成し、永続化して返す。

    encounter_id が存在しない場合は 404 を返す。
    LLM が利用できない場合は 503 を返す。
    UUID・臨床入力はエラーメッセージに含めない。
    """
    try:
        draft = await generate(body.clinical_input, encounter_id, clinician_id)
    except EncounterNotFound:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "encounter_not_found",
                "message": "Encounter not found.",
            },
        ) from None
    # InferenceError はキャッチしない — グローバルハンドラに委ねる

    return DraftRead.from_entity(draft)


@router.post(
    "/encounters/{encounter_id}/drafts/stream",
    response_class=StreamingResponse,
    status_code=200,
    responses={
        401: {"model": ErrorResponse, "description": "X-Clinician-Id ヘッダーが欠落または不正"},
        404: {"model": ErrorResponse, "description": "受診が見つからない (同期エラー)"},
        422: {"model": ErrorResponse, "description": "リクエストボディが不正"},
    },
    summary="カルテ下書きストリーミング生成 (SSE)",
)
async def post_draft_stream(
    encounter_id: UUID,
    body: DraftCreate,
    clinician_id: UUID = Depends(get_current_clinician),
    stream_draft: StreamRecordDraftCallable = Depends(make_stream_record_draft),
) -> StreamingResponse:
    """AI によるカルテ下書きを SSE でストリーミング生成する。

    SSE イベント形式:
      - 通常チャンク:   data: {"text": "...", "done": false, "confidence": null}\\n\\n
      - 完了チャンク:   event: complete\\ndata: {"draft_id": "...", "confidence": null}\\n\\n
      - エラーチャンク: event: error\\ndata: {"code": "...", "message": "..."}\\n\\n

    encounter_id が存在しない場合は 404 を返す (ストリームを開く前の同期エラー)。
    LLM が mid-stream で失敗した場合は SSE error イベントを送出してストリームを閉じる。
    UUID・臨床入力はエラーメッセージに含めない。
    """
    # (1) 受診存在確認を同期的に実施するため、EncounterNotFound は try-except で捕捉する。
    # ストリームが開いていない状態での 404 は通常の HTTP レスポンスとして返す。
    # ストリームを開いた後のエラーは SSE error イベントとして送出する。

    # EncounterNotFound をここで事前確認するために stream を一旦開始する前に
    # encounter 存在チェックを試みる必要がある。
    # しかし stream_record_draft は async generator なので、呼び出すだけではまだ実行されない。
    # EncounterNotFound は generator の最初の yield 前に raise される。
    # そのため、generator の最初のチャンクを取得しようとする際に例外が上がる。
    # TestClient は StreamingResponse の本体を読みに行くまで例外を受け取れない。
    # → 解決策: ジェネレータを wrap して最初のチャンクを先読みし、
    #   EncounterNotFound が来たら HTTP 404 を返す (ストリーム開始前)。

    gen = stream_draft(body.clinical_input, encounter_id, clinician_id)

    # 最初のチャンクを先読みして EncounterNotFound を同期的に検出する。
    # EncounterNotFound はストリーム開始前 (HTTP 404 として返す)。
    # InferenceError がすぐに来た場合は SSE error ストリームとして返す。
    _inference_error: InferenceError | None = None
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
    except InferenceError as exc:
        # 最初のチャンク取得時に InferenceError が来た場合は SSE error ストリームを返す
        _inference_error = exc
        logger.warning(
            "InferenceError at stream start encounter_id=%s: %s",
            short_id(encounter_id),
            exc.masked_context,
        )
    except StopAsyncIteration:
        # チャンクが 1 件もない場合 (通常発生しないが念のため空ストリームを返す)
        first_chunk = None

    # EncounterNotFound が来なかった場合、ストリームをラップして SSE エンコードを行う
    async def _sse_generator() -> AsyncGenerator[bytes, None]:
        # 最初のチャンク取得時に InferenceError が来た場合は error イベントだけ送出する
        if _inference_error is not None:
            yield sse_event_frame(
                "error",
                {
                    "code": "inference_unavailable",
                    "message": "Inference service is temporarily unavailable.",
                },
            )
            return

        # 先読みしたチャンクから開始する (None の場合はストリームをスキップ)
        if first_chunk is None:
            return

        current = first_chunk
        while True:
            if current.done:
                # done=True は completion チャンク: text に JSON ペイロードが入っている
                # stream_record_draft が最後に yield する completion チャンク
                yield sse_event_frame("complete", current.text)
                break
            else:
                yield sse_data_frame(
                    {
                        "text": current.text,
                        "done": current.done,
                        "confidence": current.confidence,
                    }
                )

            # 次のチャンクを取得する
            try:
                current = await gen.__anext__()
            except InferenceError as exc:
                # mid-stream InferenceError: SSE error イベントとして送出する
                # exc.masked_context には PHI マスク済みコンテキストが入っている
                logger.warning(
                    "InferenceError mid-stream encounter_id=%s: %s",
                    short_id(encounter_id),
                    exc.masked_context,
                )
                yield sse_event_frame(
                    "error",
                    {
                        "code": "inference_unavailable",
                        "message": "Inference service is temporarily unavailable.",
                    },
                )
                break
            except StopAsyncIteration:
                break

    return StreamingResponse(
        _sse_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get(
    "/drafts/{draft_id}",
    response_model=DraftRead,
    responses={
        401: {"model": ErrorResponse, "description": "X-Clinician-Id ヘッダーが欠落または不正"},
        404: {"model": ErrorResponse, "description": "下書きが見つからない"},
    },
    summary="カルテ下書き取得 (ID)",
)
async def get_draft_by_id(
    draft_id: UUID,
    _clinician_id: UUID = Depends(get_current_clinician),
    find: FindDraftByIdCallable = Depends(make_find_draft_by_id),
) -> DraftRead:
    """UUID でカルテ下書きを取得する。

    UUID はエラーメッセージに含めない。
    """
    try:
        draft = await find(draft_id)
    except DraftNotFound:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "draft_not_found",
                "message": "Draft not found.",
            },
        ) from None

    return DraftRead.from_entity(draft)


@router.patch(
    "/drafts/{draft_id}",
    response_model=DraftRead,
    responses={
        401: {"model": ErrorResponse, "description": "X-Clinician-Id ヘッダーが欠落または不正"},
        404: {"model": ErrorResponse, "description": "下書きが見つからない"},
    },
    summary="カルテ下書き編集",
)
async def patch_draft(
    draft_id: UUID,
    body: DraftEdit,
    clinician_id: UUID = Depends(get_current_clinician),
    edit: EditRecordDraftCallable = Depends(make_edit_record_draft),
) -> DraftRead:
    """臨床医によるカルテ下書きの本文編集。

    更新後の DraftRead を返す。
    UUID・content はエラーメッセージに含めない。
    """
    try:
        draft = await edit(draft_id, body.content, clinician_id)
    except DraftNotFound:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "draft_not_found",
                "message": "Draft not found.",
            },
        ) from None

    return DraftRead.from_entity(draft)


@router.post(
    "/drafts/{draft_id}/finalize",
    response_model=FinalRead,
    status_code=201,
    responses={
        401: {"model": ErrorResponse, "description": "X-Clinician-Id ヘッダーが欠落または不正"},
        404: {"model": ErrorResponse, "description": "下書きが見つからない"},
        409: {"model": ErrorResponse, "description": "受診にすでに確定カルテが存在する"},
    },
    summary="下書き確定 (確定カルテ昇格)",
)
async def post_finalize_draft(
    draft_id: UUID,
    body: FinalizeRequest,
    clinician_id: UUID = Depends(get_current_clinician),
    finalize: FinalizeDraftCallable = Depends(make_finalize_draft_to_record_final),
) -> FinalRead:
    """下書きを確定カルテに昇格させる。

    受診にすでに確定カルテが存在する場合は 409 を返す。
    UUID・content はエラーメッセージに含めない。
    レスポンスは finals ルーターの FinalRead 形式で返す。
    """
    try:
        final = await finalize(draft_id, clinician_id)
    except DraftNotFound:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "draft_not_found",
                "message": "Draft not found.",
            },
        ) from None
    except EncounterAlreadyFinalized:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "encounter_already_finalized",
                "message": "Encounter already has a finalized record.",
            },
        ) from None

    return FinalRead.from_entity(final)
