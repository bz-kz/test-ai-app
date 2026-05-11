"""カルテ下書きエンドポイントルーター。

POST /encounters/{encounter_id}/drafts   — AI 生成下書きの作成
GET  /drafts/{draft_id}                 — UUID による下書き取得

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

from app.interfaces.schemas import ErrorResponse
from app.usecases.di import (
    FindDraftByIdCallable,
    GenerateRecordDraftCallable,
    make_find_draft_by_id,
    make_generate_record_draft,
)
from app.usecases.errors import DraftNotFound, EncounterNotFound

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
