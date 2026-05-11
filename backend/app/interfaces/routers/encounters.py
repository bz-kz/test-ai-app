"""受診エンドポイントルーター。

POST /encounters                          — 受診作成 (create_encounter ユースケース呼び出し)
GET  /encounters/{encounter_id}           — UUID による受診取得
GET  /patients/{patient_id}/encounters   — 患者に紐づく受診一覧

PHI ルール:
  - encounter と patient の紐づきは PHI (local-llm-and-phi.md §3)。
  - エラーメッセージには UUID を一切含めない。
  - ログ出力は id のみ; MRN・氏名など他の PHI は流入しない。
  - 監査ログ meta_json は "{}" で固定 (patient_id を含まない)。

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
from app.usecases.di import (
    CreateEncounterCallable,
    FindEncounterByIdCallable,
    ListEncountersByPatientCallable,
    make_create_encounter,
    make_find_encounter_by_id,
    make_list_encounters_by_patient,
)
from app.usecases.errors import EncounterNotFound, PatientNotFound

logger = logging.getLogger(__name__)

router = APIRouter(tags=["encounters"])


# ---------------------------------------------------------------------------
# Pydantic モデル
# ---------------------------------------------------------------------------


class EncounterCreate(BaseModel):
    """受診作成リクエストボディ。"""

    model_config = ConfigDict(extra="forbid")

    patient_id: UUID
    encountered_at: datetime
    clinician_id: UUID


class EncounterRead(BaseModel):
    """受診レスポンス。呼び出し元が明示的に受診を要求した際にのみ返す。"""

    id: UUID
    patient_id: UUID
    encountered_at: datetime
    clinician_id: UUID
    created_at: datetime


# ---------------------------------------------------------------------------
# エンドポイント
# ---------------------------------------------------------------------------


@router.post(
    "/encounters",
    response_model=EncounterRead,
    status_code=201,
    responses={
        404: {"model": ErrorResponse, "description": "患者が見つからない"},
        422: {"model": ErrorResponse, "description": "リクエストのバリデーションエラー"},
    },
    summary="受診作成",
)
async def post_encounter(
    body: EncounterCreate,
    create: CreateEncounterCallable = Depends(make_create_encounter),
) -> EncounterRead:
    """新規受診を作成し、監査ログを記録する (create_encounter ユースケース)。

    patient_id が存在しない場合は 404 を返す。UUID はエラーメッセージに含めない。
    """
    try:
        encounter = await create(
            body.patient_id,
            body.encountered_at,
            body.clinician_id,
        )
    except PatientNotFound:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "patient_not_found",
                "message": "Patient not found.",
            },
        ) from None

    return EncounterRead(
        id=encounter.id,
        patient_id=encounter.patient_id,
        encountered_at=encounter.encountered_at,
        clinician_id=encounter.clinician_id,
        created_at=encounter.created_at,
    )


@router.get(
    "/encounters/{encounter_id}",
    response_model=EncounterRead,
    responses={
        404: {"model": ErrorResponse, "description": "受診が見つからない"},
    },
    summary="受診取得 (ID)",
)
async def get_encounter_by_id(
    encounter_id: UUID,
    find: FindEncounterByIdCallable = Depends(make_find_encounter_by_id),
) -> EncounterRead:
    """UUID で受診を取得する (find_encounter_by_id ユースケース)。

    UUID はエラーメッセージに含めない。
    """
    try:
        encounter = await find(encounter_id)
    except EncounterNotFound:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "encounter_not_found",
                "message": "Encounter not found.",
            },
        ) from None

    return EncounterRead(
        id=encounter.id,
        patient_id=encounter.patient_id,
        encountered_at=encounter.encountered_at,
        clinician_id=encounter.clinician_id,
        created_at=encounter.created_at,
    )


@router.get(
    "/patients/{patient_id}/encounters",
    response_model=list[EncounterRead],
    responses={
        404: {"model": ErrorResponse, "description": "患者が見つからない"},
    },
    summary="患者の受診一覧",
)
async def get_encounters_by_patient(
    patient_id: UUID,
    list_enc: ListEncountersByPatientCallable = Depends(make_list_encounters_by_patient),
) -> list[EncounterRead]:
    """患者に紐づく受診を encountered_at 降順で返す (list_encounters_by_patient ユースケース)。

    受診がない場合は空リスト (404 ではない)。患者が存在しない場合は 404。
    UUID はエラーメッセージに含めない。
    """
    try:
        encounters = await list_enc(patient_id)
    except PatientNotFound:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "patient_not_found",
                "message": "Patient not found.",
            },
        ) from None

    return [
        EncounterRead(
            id=e.id,
            patient_id=e.patient_id,
            encountered_at=e.encountered_at,
            clinician_id=e.clinician_id,
            created_at=e.created_at,
        )
        for e in encounters
    ]
