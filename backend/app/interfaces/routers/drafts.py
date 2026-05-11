"""カルテ下書きエンドポイントルーター。

POST /encounters/{encounter_id}/drafts   — AI 生成下書きの作成
GET  /drafts/{draft_id}                 — UUID による下書き取得
PATCH /drafts/{draft_id}               — 臨床医による下書き編集
POST /drafts/{draft_id}/finalize        — 下書きを確定カルテに昇格

PHI ルール:
  - clinical_input および draft.content は PHI (自由記述の臨床叙述)。
  - エラーメッセージには UUID・臨床入力・下書き内容を一切含めない。
  - レスポンスの content フィールドは PHI だが、呼び出し元が明示的に下書きを要求したため
    返却が許可される (local-llm-and-phi.md §4 操作的読み取り)。
  - InferenceError は グローバルハンドラ (inference_error_handler) が 503 に変換する。

レイヤー方向:
  interfaces → usecases のみ。infrastructure は直接参照しない。
"""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.interfaces.routers.finals import FinalRead
from app.interfaces.schemas import ErrorResponse
from app.usecases.di import (
    EditRecordDraftCallable,
    FinalizeDraftCallable,
    FindDraftByIdCallable,
    GenerateRecordDraftCallable,
    make_edit_record_draft,
    make_finalize_draft_to_record_final,
    make_find_draft_by_id,
    make_generate_record_draft,
)
from app.usecases.errors import DraftNotFound, EncounterAlreadyFinalized, EncounterNotFound

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


class DraftEdit(BaseModel):
    """下書き編集リクエストボディ。

    content は PHI を含む臨床叙述。空文字列は不可。
    clinician_id は認証機能未実装のためリクエストボディで受け取る。
    将来の auth Block でヘッダー/セッションから注入する予定。
    """

    model_config = ConfigDict(extra="forbid")

    content: str = Field(..., min_length=1)
    clinician_id: UUID


class FinalizeRequest(BaseModel):
    """下書き確定リクエストボディ。

    clinician_id は認証機能未実装のためリクエストボディで受け取る。
    将来の auth Block でヘッダー/セッションから注入する予定。
    """

    model_config = ConfigDict(extra="forbid")

    clinician_id: UUID


# ---------------------------------------------------------------------------
# エンドポイント
# ---------------------------------------------------------------------------


@router.post(
    "/encounters/{encounter_id}/drafts",
    response_model=DraftRead,
    status_code=201,
    responses={
        404: {"model": ErrorResponse, "description": "受診が見つからない"},
        503: {"model": ErrorResponse, "description": "推論サービス一時利用不可"},
    },
    summary="カルテ下書き生成",
)
async def post_draft(
    encounter_id: UUID,
    body: DraftCreate,
    generate: GenerateRecordDraftCallable = Depends(make_generate_record_draft),
) -> DraftRead:
    """AI によるカルテ下書きを生成し、永続化して返す。

    encounter_id が存在しない場合は 404 を返す。
    LLM が利用できない場合は 503 を返す。
    UUID・臨床入力はエラーメッセージに含めない。
    """
    try:
        draft = await generate(body.clinical_input, encounter_id)
    except EncounterNotFound:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "encounter_not_found",
                "message": "Encounter not found.",
            },
        ) from None
    # InferenceError はキャッチしない — グローバルハンドラに委ねる

    return DraftRead(
        id=draft.id,
        encounter_id=draft.encounter_id,
        content=draft.content,
        confidence=draft.confidence,
        created_at=draft.created_at,
        updated_at=draft.updated_at,
    )


@router.get(
    "/drafts/{draft_id}",
    response_model=DraftRead,
    responses={
        404: {"model": ErrorResponse, "description": "下書きが見つからない"},
    },
    summary="カルテ下書き取得 (ID)",
)
async def get_draft_by_id(
    draft_id: UUID,
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

    return DraftRead(
        id=draft.id,
        encounter_id=draft.encounter_id,
        content=draft.content,
        confidence=draft.confidence,
        created_at=draft.created_at,
        updated_at=draft.updated_at,
    )


@router.patch(
    "/drafts/{draft_id}",
    response_model=DraftRead,
    responses={
        404: {"model": ErrorResponse, "description": "下書きが見つからない"},
    },
    summary="カルテ下書き編集",
)
async def patch_draft(
    draft_id: UUID,
    body: DraftEdit,
    edit: EditRecordDraftCallable = Depends(make_edit_record_draft),
) -> DraftRead:
    """臨床医によるカルテ下書きの本文編集。

    更新後の DraftRead を返す。
    UUID・content はエラーメッセージに含めない。
    """
    try:
        draft = await edit(draft_id, body.content, body.clinician_id)
    except DraftNotFound:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "draft_not_found",
                "message": "Draft not found.",
            },
        ) from None

    return DraftRead(
        id=draft.id,
        encounter_id=draft.encounter_id,
        content=draft.content,
        confidence=draft.confidence,
        created_at=draft.created_at,
        updated_at=draft.updated_at,
    )


@router.post(
    "/drafts/{draft_id}/finalize",
    response_model=FinalRead,
    status_code=201,
    responses={
        404: {"model": ErrorResponse, "description": "下書きが見つからない"},
        409: {"model": ErrorResponse, "description": "受診にすでに確定カルテが存在する"},
    },
    summary="下書き確定 (確定カルテ昇格)",
)
async def post_finalize_draft(
    draft_id: UUID,
    body: FinalizeRequest,
    finalize: FinalizeDraftCallable = Depends(make_finalize_draft_to_record_final),
) -> FinalRead:
    """下書きを確定カルテに昇格させる。

    受診にすでに確定カルテが存在する場合は 409 を返す。
    UUID・content はエラーメッセージに含めない。
    レスポンスは finals ルーターの FinalRead 形式で返す。
    """
    try:
        final = await finalize(draft_id, body.clinician_id)
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

    return FinalRead(
        id=final.id,
        encounter_id=final.encounter_id,
        content=final.content,
        confidence=final.confidence,
        clinician_id=final.clinician_id,
        predecessor_id=final.predecessor_id,
        created_at=final.created_at,
    )
