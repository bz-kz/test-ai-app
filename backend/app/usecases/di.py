"""ユースケース層の FastAPI DI サーフェス。

interfaces 層はここからのみ依存性を取得する。
infrastructure 層を直接参照しない。
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable, Coroutine
from datetime import date, datetime
from typing import Any
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Encounter, Patient
from app.infrastructure.db.engine import get_session
from app.infrastructure.db.repositories import (
    AuditLogRepository,
    EncounterRepository,
    PatientRepository,
)
from app.usecases.encounter import (
    create_encounter,
    find_encounter_by_id,
    list_encounters_by_patient,
)
from app.usecases.patient import create_patient, find_patient_by_id, find_patient_by_mrn

# ---------------------------------------------------------------------------
# セッション依存 (usecases.di 経由でのみ interfaces 層に公開する)
# ---------------------------------------------------------------------------


async def _get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI Depends 経由でセッションを提供する (infrastructure エンジンをラップ)。"""
    async for session in get_session():
        yield session


# ---------------------------------------------------------------------------
# ユースケースファクトリ型エイリアス
# ---------------------------------------------------------------------------

CreatePatientCallable = Callable[
    [str, str, str, date],
    Coroutine[Any, Any, Patient],
]

FindPatientByIdCallable = Callable[
    [UUID],
    Coroutine[Any, Any, Patient | None],
]

FindPatientByMrnCallable = Callable[
    [str],
    Coroutine[Any, Any, Patient | None],
]


# ---------------------------------------------------------------------------
# ユースケースファクトリ依存
# interfaces 層はこれらを Depends() で取得し、呼び出す。
# ---------------------------------------------------------------------------


def make_create_patient(
    session: AsyncSession = Depends(_get_db_session),
) -> CreatePatientCallable:
    """create_patient ユースケースをセッション付きでクロージャとして返す。"""
    patient_repo = PatientRepository(session)
    audit_repo = AuditLogRepository(session)

    async def _create(
        mrn: str,
        family_name: str,
        given_name: str,
        date_of_birth: date,
    ) -> Patient:
        patient = await create_patient(
            mrn=mrn,
            family_name=family_name,
            given_name=given_name,
            date_of_birth=date_of_birth,
            patient_repo=patient_repo,
            audit_repo=audit_repo,
        )
        await session.commit()
        return patient

    return _create


def make_find_patient_by_id(
    session: AsyncSession = Depends(_get_db_session),
) -> FindPatientByIdCallable:
    """find_patient_by_id ユースケースをセッション付きでクロージャとして返す。"""
    patient_repo = PatientRepository(session)

    async def _find(patient_id: UUID) -> Patient | None:
        return await find_patient_by_id(
            patient_id=patient_id,
            patient_repo=patient_repo,
        )

    return _find


def make_find_patient_by_mrn(
    session: AsyncSession = Depends(_get_db_session),
) -> FindPatientByMrnCallable:
    """find_patient_by_mrn ユースケースをセッション付きでクロージャとして返す。"""
    patient_repo = PatientRepository(session)

    async def _find(mrn: str) -> Patient | None:
        return await find_patient_by_mrn(
            mrn=mrn,
            patient_repo=patient_repo,
        )

    return _find


# ---------------------------------------------------------------------------
# 受診ユースケースファクトリ型エイリアス
# ---------------------------------------------------------------------------

CreateEncounterCallable = Callable[
    [UUID, datetime, UUID],
    Coroutine[Any, Any, Encounter],
]

FindEncounterByIdCallable = Callable[
    [UUID],
    Coroutine[Any, Any, Encounter],
]

ListEncountersByPatientCallable = Callable[
    [UUID],
    Coroutine[Any, Any, list[Encounter]],
]


# ---------------------------------------------------------------------------
# 受診ユースケースファクトリ依存
# ---------------------------------------------------------------------------


def make_create_encounter(
    session: AsyncSession = Depends(_get_db_session),
) -> CreateEncounterCallable:
    """create_encounter ユースケースをセッション付きでクロージャとして返す。"""
    patient_repo = PatientRepository(session)
    encounter_repo = EncounterRepository(session)
    audit_repo = AuditLogRepository(session)

    async def _create(
        patient_id: UUID,
        encountered_at: datetime,
        clinician_id: UUID,
    ) -> Encounter:
        encounter = await create_encounter(
            patient_id=patient_id,
            encountered_at=encountered_at,
            clinician_id=clinician_id,
            patient_repo=patient_repo,
            encounter_repo=encounter_repo,
            audit_repo=audit_repo,
        )
        await session.commit()
        return encounter

    return _create


def make_find_encounter_by_id(
    session: AsyncSession = Depends(_get_db_session),
) -> FindEncounterByIdCallable:
    """find_encounter_by_id ユースケースをセッション付きでクロージャとして返す。"""
    encounter_repo = EncounterRepository(session)

    async def _find(encounter_id: UUID) -> Encounter:
        return await find_encounter_by_id(
            encounter_id=encounter_id,
            encounter_repo=encounter_repo,
        )

    return _find


def make_list_encounters_by_patient(
    session: AsyncSession = Depends(_get_db_session),
) -> ListEncountersByPatientCallable:
    """list_encounters_by_patient ユースケースをセッション付きでクロージャとして返す。"""
    patient_repo = PatientRepository(session)
    encounter_repo = EncounterRepository(session)

    async def _list(patient_id: UUID) -> list[Encounter]:
        return await list_encounters_by_patient(
            patient_id=patient_id,
            patient_repo=patient_repo,
            encounter_repo=encounter_repo,
        )

    return _list
