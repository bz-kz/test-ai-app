"""患者エンドポイントルーター。

POST /patients        — 患者作成 (create_patient ユースケース呼び出し)
GET  /patients/{id}   — UUID による患者取得 (find_patient_by_id ユースケース呼び出し)
GET  /patients?mrn=   — MRN による患者取得 (find_patient_by_mrn ユースケース呼び出し)

PHI ルール:
  - mrn / family_name / given_name / date_of_birth はリクエスト/レスポンス本文にのみ存在する。
  - エラーメッセージには PHI 値を一切含めない。
  - ログ出力前に mask_phi() を通す。
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.engine import get_session
from app.infrastructure.db.repositories import AuditLogRepository, PatientRepository
from app.interfaces.schemas import ErrorResponse
from app.usecases.patient import create_patient, find_patient_by_id, find_patient_by_mrn

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
# 依存性注入ヘルパー
# ---------------------------------------------------------------------------


async def _get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI Depends 経由でセッションを提供する。"""
    async for session in get_session():
        yield session


# ---------------------------------------------------------------------------
# エンドポイント
# ---------------------------------------------------------------------------


@router.post(
    "/patients",
    response_model=PatientRead,
    status_code=201,
    responses={
        409: {"model": ErrorResponse, "description": "MRN が既存患者と重複する"},
        422: {"model": ErrorResponse, "description": "リクエストのバリデーションエラー"},
    },
    summary="患者作成",
)
async def post_patient(
    body: PatientCreate,
    session: AsyncSession = Depends(_get_db_session),
) -> PatientRead:
    """新規患者を作成し、監査ログを記録する (create_patient ユースケース)。

    PHI MUST NOT be echoed in error messages.
    MRN 重複の場合は 409 を返す (MRN 値はエラーメッセージに含めない)。
    """
    patient_repo = PatientRepository(session)
    audit_repo = AuditLogRepository(session)

    # MRN 重複チェック: 先に検索して重複を検出する
    existing = await patient_repo.find_by_mrn(body.mrn)
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "patient_mrn_conflict",
                "message": "A patient with this MRN already exists.",
            },
        )

    patient = await create_patient(
        mrn=body.mrn,
        family_name=body.family_name,
        given_name=body.given_name,
        date_of_birth=body.date_of_birth,
        patient_repo=patient_repo,
        audit_repo=audit_repo,
    )
    await session.commit()

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
        404: {"model": ErrorResponse, "description": "患者が見つからない"},
    },
    summary="患者取得 (ID)",
)
async def get_patient_by_id(
    patient_id: UUID,
    session: AsyncSession = Depends(_get_db_session),
) -> PatientRead:
    """UUID で患者を取得する (find_patient_by_id ユースケース)。

    PHI MUST NOT be echoed in error messages.
    """
    patient_repo = PatientRepository(session)

    patient = await find_patient_by_id(
        patient_id=patient_id,
        patient_repo=patient_repo,
    )
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
        404: {"model": ErrorResponse, "description": "患者が見つからない"},
    },
    summary="患者取得 (MRN)",
)
async def get_patient_by_mrn(
    mrn: str = Query(..., min_length=1, description="診察番号 (PHI)"),
    session: AsyncSession = Depends(_get_db_session),
) -> PatientRead:
    """MRN で患者を取得する (find_patient_by_mrn ユースケース)。

    PHI MUST NOT be echoed in error messages.
    """
    patient_repo = PatientRepository(session)

    patient = await find_patient_by_mrn(
        mrn=mrn,
        patient_repo=patient_repo,
    )
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
