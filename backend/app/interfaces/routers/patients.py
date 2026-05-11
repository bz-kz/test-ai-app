"""患者エンドポイントルーター。

POST /patients        — 患者作成 (create_patient ユースケース呼び出し)
GET  /patients/{id}   — UUID による患者取得 (find_patient_by_id ユースケース呼び出し)
GET  /patients?mrn=   — MRN による患者取得 (find_patient_by_mrn ユースケース呼び出し)

PHI ルール:
  - mrn / family_name / given_name / date_of_birth はリクエスト/レスポンス本文にのみ存在する。
  - エラーメッセージには PHI 値を一切含めない。
  - ログ出力前に mask_phi() を通す。

レイヤー方向:
  interfaces → usecases のみ。infrastructure は直接参照しない。
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.interfaces.auth import get_current_clinician
from app.interfaces.schemas import ErrorResponse
from app.usecases.di import (
    CreatePatientCallable,
    FindPatientByIdCallable,
    FindPatientByMrnCallable,
    make_create_patient,
    make_find_patient_by_id,
    make_find_patient_by_mrn,
)
from app.usecases.errors import MRNConflict

logger = logging.getLogger(__name__)

router = APIRouter(tags=["patients"])


# ---------------------------------------------------------------------------
# Pydantic モデル
# ---------------------------------------------------------------------------


class PatientCreate(BaseModel):
    """患者作成リクエストボディ。全フィールドが PHI。"""

    mrn: str
    family_name: str
    given_name: str
    date_of_birth: date


class PatientRead(BaseModel):
    """患者レスポンス。呼び出し元が明示的に患者を要求した際にのみ返す。"""

    id: UUID
    mrn: str
    family_name: str
    given_name: str
    date_of_birth: date
    created_at: datetime


# ---------------------------------------------------------------------------
# エンドポイント
# ---------------------------------------------------------------------------


@router.post(
    "/patients",
    response_model=PatientRead,
    status_code=201,
    responses={
        401: {"model": ErrorResponse, "description": "X-Clinician-Id ヘッダーが欠落または不正"},
        409: {"model": ErrorResponse, "description": "MRN が既存患者と重複する"},
        422: {"model": ErrorResponse, "description": "リクエストのバリデーションエラー"},
    },
    summary="患者作成",
)
async def post_patient(
    body: PatientCreate,
    clinician_id: UUID = Depends(get_current_clinician),
    create: CreatePatientCallable = Depends(make_create_patient),
) -> PatientRead:
    """新規患者を作成し、監査ログを記録する (create_patient ユースケース)。

    PHI MUST NOT be echoed in error messages.
    MRN 重複の場合は 409 を返す (MRN 値はエラーメッセージに含めない)。
    """
    try:
        patient = await create(
            body.mrn,
            body.family_name,
            body.given_name,
            body.date_of_birth,
            clinician_id,
        )
    except MRNConflict:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "patient_mrn_conflict",
                "message": "A patient with this MRN already exists.",
            },
        ) from None

    return PatientRead(
        id=patient.id,
        mrn=patient.mrn,
        family_name=patient.family_name,
        given_name=patient.given_name,
        # domain entity は datetime(UTC midnight); date に変換して返す
        date_of_birth=patient.date_of_birth.date(),
        created_at=patient.created_at,
    )


@router.get(
    "/patients/{patient_id}",
    response_model=PatientRead,
    responses={
        401: {"model": ErrorResponse, "description": "X-Clinician-Id ヘッダーが欠落または不正"},
        404: {"model": ErrorResponse, "description": "患者が見つからない"},
    },
    summary="患者取得 (ID)",
)
async def get_patient_by_id(
    patient_id: UUID,
    _clinician_id: UUID = Depends(get_current_clinician),
    find: FindPatientByIdCallable = Depends(make_find_patient_by_id),
) -> PatientRead:
    """UUID で患者を取得する (find_patient_by_id ユースケース)。

    PHI MUST NOT be echoed in error messages.
    """
    patient = await find(patient_id)
    if patient is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "patient_not_found", "message": "Patient not found."},
        )

    return PatientRead(
        id=patient.id,
        mrn=patient.mrn,
        family_name=patient.family_name,
        given_name=patient.given_name,
        date_of_birth=patient.date_of_birth.date(),
        created_at=patient.created_at,
    )


@router.get(
    "/patients",
    response_model=PatientRead,
    responses={
        401: {"model": ErrorResponse, "description": "X-Clinician-Id ヘッダーが欠落または不正"},
        404: {"model": ErrorResponse, "description": "患者が見つからない"},
    },
    summary="患者取得 (MRN)",
)
async def get_patient_by_mrn(
    mrn: str = Query(..., min_length=1, description="診察番号 (PHI)"),
    _clinician_id: UUID = Depends(get_current_clinician),
    find: FindPatientByMrnCallable = Depends(make_find_patient_by_mrn),
) -> PatientRead:
    """MRN で患者を取得する (find_patient_by_mrn ユースケース)。

    PHI MUST NOT be echoed in error messages.
    """
    patient = await find(mrn)
    if patient is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "patient_not_found", "message": "Patient not found."},
        )

    return PatientRead(
        id=patient.id,
        mrn=patient.mrn,
        family_name=patient.family_name,
        given_name=patient.given_name,
        date_of_birth=patient.date_of_birth.date(),
        created_at=patient.created_at,
    )
