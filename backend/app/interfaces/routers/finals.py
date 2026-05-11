"""確定カルテエンドポイントルーター (BE-007)。

GET /finals/{final_id}  — UUID による確定カルテ取得

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
from pydantic import BaseModel, ConfigDict

from app.interfaces.schemas import ErrorResponse
from app.usecases.di import FindFinalByIdCallable, make_find_final_by_id
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


# ---------------------------------------------------------------------------
# エンドポイント
# ---------------------------------------------------------------------------


@router.get(
    "/finals/{final_id}",
    response_model=FinalRead,
    responses={
        404: {"model": ErrorResponse, "description": "確定カルテが見つからない"},
    },
    summary="確定カルテ取得 (ID)",
)
async def get_final_by_id(
    final_id: UUID,
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
