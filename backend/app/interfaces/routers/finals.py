"""確定カルテエンドポイントルーター (BE-007, BE-008)。

GET  /finals/{final_id}          — UUID による確定カルテ取得
POST /finals/{final_id}/correct  — 確定カルテの訂正版作成
GET  /finals/{final_id}/chain    — predecessor チェーン取得 (最古→指定版)

PHI ルール:
  - final.content は PHI (自由記述の臨床叙述)。
  - エラーメッセージには UUID・内容を一切含めない。
  - レスポンスの content フィールドは PHI だが、呼び出し元が明示的に要求したため
    返却が許可される (local-llm-and-phi.md §4 操作的読み取り)。

レイヤー方向:
  interfaces → usecases のみ。infrastructure は直接参照しない。
"""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.interfaces.auth import get_current_clinician
from app.interfaces.schemas import ErrorResponse
from app.usecases.di import (
    CorrectRecordFinalCallable,
    FindChainForFinalCallable,
    FindFinalByIdCallable,
    make_correct_record_final,
    make_find_chain_for_final,
    make_find_final_by_id,
)
from app.usecases.errors import FinalNotFound

logger = logging.getLogger(__name__)

router = APIRouter(tags=["finals"])


# ---------------------------------------------------------------------------
# Pydantic モデル
# ---------------------------------------------------------------------------


class FinalRead(BaseModel):
    """確定カルテレスポンス。

    content は PHI だが、呼び出し元が明示的にこのエンドポイントを叩いたため返却する
    (local-llm-and-phi.md §4 操作的読み取り)。
    """

    model_config = ConfigDict()

    id: UUID
    encounter_id: UUID
    content: str
    confidence: float | None
    clinician_id: UUID
    predecessor_id: UUID | None
    created_at: datetime


class FinalCorrectRequest(BaseModel):
    """確定カルテ訂正リクエストボディ (BE-008)。

    clinician_id はヘッダーから注入するためボディに含めない。
    """

    model_config = ConfigDict(extra="forbid")

    content: str = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# エンドポイント
# ---------------------------------------------------------------------------


@router.get(
    "/finals/{final_id}",
    response_model=FinalRead,
    responses={
        401: {"model": ErrorResponse, "description": "X-Clinician-Id ヘッダーが欠落または不正"},
        404: {"model": ErrorResponse, "description": "確定カルテが見つからない"},
    },
    summary="確定カルテ取得 (ID)",
)
async def get_final_by_id(
    final_id: UUID,
    _clinician_id: UUID = Depends(get_current_clinician),
    find: FindFinalByIdCallable = Depends(make_find_final_by_id),
) -> FinalRead:
    """UUID で確定カルテを取得する。

    UUID はエラーメッセージに含めない。
    """
    try:
        final = await find(final_id)
    except FinalNotFound:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "final_not_found",
                "message": "Final not found.",
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


@router.post(
    "/finals/{final_id}/correct",
    response_model=FinalRead,
    status_code=201,
    responses={
        401: {"model": ErrorResponse, "description": "X-Clinician-Id ヘッダーが欠落または不正"},
        404: {"model": ErrorResponse, "description": "訂正元確定カルテが見つからない"},
        422: {"model": ErrorResponse, "description": "リクエストのバリデーションエラー"},
    },
    summary="確定カルテ訂正版作成",
)
async def post_correct_final(
    final_id: UUID,
    body: FinalCorrectRequest,
    clinician_id: UUID = Depends(get_current_clinician),
    correct: CorrectRecordFinalCallable = Depends(make_correct_record_final),
) -> FinalRead:
    """訂正元確定カルテ ID を指定して訂正版を作成する (BE-008)。

    訂正版は predecessor_id で元版と連鎖する。confidence は None (人間編集のため)。
    UUID はエラーメッセージに含めない。
    """
    try:
        new_final = await correct(final_id, body.content, clinician_id)
    except FinalNotFound:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "final_not_found",
                "message": "Final not found.",
            },
        ) from None

    return FinalRead(
        id=new_final.id,
        encounter_id=new_final.encounter_id,
        content=new_final.content,
        confidence=new_final.confidence,
        clinician_id=new_final.clinician_id,
        predecessor_id=new_final.predecessor_id,
        created_at=new_final.created_at,
    )


@router.get(
    "/finals/{final_id}/chain",
    response_model=list[FinalRead],
    responses={
        401: {"model": ErrorResponse, "description": "X-Clinician-Id ヘッダーが欠落または不正"},
        404: {"model": ErrorResponse, "description": "確定カルテが見つからない"},
    },
    summary="確定カルテ predecessor チェーン取得",
)
async def get_final_chain(
    final_id: UUID,
    _clinician_id: UUID = Depends(get_current_clinician),
    find_chain: FindChainForFinalCallable = Depends(make_find_chain_for_final),
) -> list[FinalRead]:
    """指定 ID の確定カルテを起点に predecessor チェーンを返す (BE-008)。

    返却順は [最古版, ..., 指定版] の昇順 (created_at 昇順)。
    UUID はエラーメッセージに含めない。
    """
    try:
        chain = await find_chain(final_id)
    except FinalNotFound:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "final_not_found",
                "message": "Final not found.",
            },
        ) from None

    return [
        FinalRead(
            id=f.id,
            encounter_id=f.encounter_id,
            content=f.content,
            confidence=f.confidence,
            clinician_id=f.clinician_id,
            predecessor_id=f.predecessor_id,
            created_at=f.created_at,
        )
        for f in chain
    ]
