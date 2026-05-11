"""患者ユースケースのユニットテスト。

インメモリ SQLite を使い、Postgres なしで実行できる。
BE-004 Acceptance:
  (a) create_patient が Patient エンティティを返す
  (b) create_patient が AuditLog を 1 件書く
  (c) MRN 重複時に既存患者が返る (呼び出し元が重複判定できること)
  (d) find_patient_by_id が存在する/しない患者を正しく返す
  (e) find_patient_by_mrn が存在する/しない患者を正しく返す
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.domain.entities import AuditAction
from app.infrastructure.db.engine import Base
from app.infrastructure.db.repositories import AuditLogRepository, PatientRepository
from app.usecases.patient import (
    create_patient,
    find_patient_by_id,
    find_patient_by_mrn,
)


@pytest.fixture()
async def session() -> AsyncGenerator[AsyncSession, None]:
    """インメモリ SQLite セッション。各テストで独立した DB を使う。"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


# ---------------------------------------------------------------------------
# (a) create_patient が Patient エンティティを返す
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_patient_returns_entity(session: AsyncSession) -> None:
    """create_patient が正しいフィールドを持つ Patient を返す。"""
    patient_repo = PatientRepository(session)
    audit_repo = AuditLogRepository(session)

    dob = date(1985, 4, 10)
    patient = await create_patient(
        mrn="MRN-UC-P001",
        family_name="山田",
        given_name="太郎",
        date_of_birth=dob,
        patient_repo=patient_repo,
        audit_repo=audit_repo,
    )
    await session.flush()

    assert patient.mrn == "MRN-UC-P001"
    assert patient.family_name == "山田"
    assert patient.given_name == "太郎"
    # domain entity の date_of_birth は UTC midnight datetime
    assert patient.date_of_birth.date() == dob
    assert patient.id is not None
    assert patient.created_at is not None

    # DB から再取得して永続化されていることを確認する
    found = await patient_repo.find_by_id(patient.id)
    assert found is not None
    assert found.mrn == "MRN-UC-P001"


# ---------------------------------------------------------------------------
# (b) create_patient が AuditLog を 1 件書く
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_patient_writes_one_audit_log(session: AsyncSession) -> None:
    """create_patient が PATIENT_CREATE の監査ログを 1 件書く。"""
    patient_repo = PatientRepository(session)
    audit_repo = AuditLogRepository(session)

    patient = await create_patient(
        mrn="MRN-UC-P002",
        family_name="鈴木",
        given_name="花子",
        date_of_birth=date(1990, 6, 15),
        patient_repo=patient_repo,
        audit_repo=audit_repo,
    )
    await session.flush()

    logs = await audit_repo.list_by_target("patient", patient.id)
    assert len(logs) == 1
    assert logs[0].action == AuditAction.PATIENT_CREATE
    assert logs[0].target_kind == "patient"
    assert logs[0].target_id == patient.id
    # PHI を含まないメタデータ
    assert logs[0].meta_json == "{}"


# ---------------------------------------------------------------------------
# (c) MRN 重複時に既存患者が見つかる
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_find_by_mrn_returns_existing_on_duplicate(session: AsyncSession) -> None:
    """同一 MRN での find_by_mrn が既存患者を返す (重複検出に使う)。"""
    patient_repo = PatientRepository(session)
    audit_repo = AuditLogRepository(session)

    await create_patient(
        mrn="MRN-DUPLICATE",
        family_name="佐藤",
        given_name="一郎",
        date_of_birth=date(1975, 3, 20),
        patient_repo=patient_repo,
        audit_repo=audit_repo,
    )
    await session.flush()

    # 同じ MRN での検索は既存患者を返す
    existing = await patient_repo.find_by_mrn("MRN-DUPLICATE")
    assert existing is not None


# ---------------------------------------------------------------------------
# (d) find_patient_by_id が存在する/しない患者を返す
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_find_patient_by_id_returns_entity(session: AsyncSession) -> None:
    """find_patient_by_id が存在する患者を返す。"""
    patient_repo = PatientRepository(session)
    audit_repo = AuditLogRepository(session)

    patient = await create_patient(
        mrn="MRN-UC-P003",
        family_name="田中",
        given_name="美穂",
        date_of_birth=date(2000, 12, 5),
        patient_repo=patient_repo,
        audit_repo=audit_repo,
    )
    await session.flush()

    found = await find_patient_by_id(
        patient_id=patient.id,
        patient_repo=patient_repo,
    )
    assert found is not None
    assert found.id == patient.id


@pytest.mark.asyncio
async def test_find_patient_by_id_returns_none_on_miss(session: AsyncSession) -> None:
    """find_patient_by_id が存在しない ID で None を返す。"""
    patient_repo = PatientRepository(session)

    result = await find_patient_by_id(
        patient_id=uuid4(),
        patient_repo=patient_repo,
    )
    assert result is None


# ---------------------------------------------------------------------------
# (e) find_patient_by_mrn が存在する/しない患者を返す
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_find_patient_by_mrn_returns_entity(session: AsyncSession) -> None:
    """find_patient_by_mrn が存在する患者を返す。"""
    patient_repo = PatientRepository(session)
    audit_repo = AuditLogRepository(session)

    patient = await create_patient(
        mrn="MRN-UC-P004",
        family_name="高橋",
        given_name="誠",
        date_of_birth=date(1965, 8, 8),
        patient_repo=patient_repo,
        audit_repo=audit_repo,
    )
    await session.flush()

    found = await find_patient_by_mrn(
        mrn="MRN-UC-P004",
        patient_repo=patient_repo,
    )
    assert found is not None
    assert found.id == patient.id


@pytest.mark.asyncio
async def test_find_patient_by_mrn_returns_none_on_miss(session: AsyncSession) -> None:
    """find_patient_by_mrn が存在しない MRN で None を返す。"""
    patient_repo = PatientRepository(session)

    result = await find_patient_by_mrn(
        mrn="MRN-NONEXISTENT",
        patient_repo=patient_repo,
    )
    assert result is None


# ---------------------------------------------------------------------------
# (f) create_patient の audit_log が同一トランザクションで書かれる
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_patient_audit_same_transaction(session: AsyncSession) -> None:
    """flush 前に audit_log が pending 状態で存在する (commit 前に参照可能)。"""
    patient_repo = PatientRepository(session)
    audit_repo = AuditLogRepository(session)

    patient = await create_patient(
        mrn="MRN-UC-P005",
        family_name="伊藤",
        given_name="美咲",
        date_of_birth=date(1995, 7, 22),
        patient_repo=patient_repo,
        audit_repo=audit_repo,
    )
    await session.flush()

    # flush 後、commit 前でも患者と監査ログが見える
    p = await patient_repo.find_by_id(patient.id)
    assert p is not None

    logs = await audit_repo.list_by_target("patient", patient.id)
    assert len(logs) == 1


# ---------------------------------------------------------------------------
# (g) create_patient の created_at が UTC タイムゾーン付きであること
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_patient_created_at_is_utc(session: AsyncSession) -> None:
    """create_patient が返す Patient の created_at が UTC タイムゾーン付きであること。"""
    patient_repo = PatientRepository(session)
    audit_repo = AuditLogRepository(session)

    patient = await create_patient(
        mrn="MRN-UC-P006",
        family_name="渡辺",
        given_name="健",
        date_of_birth=date(1980, 1, 1),
        patient_repo=patient_repo,
        audit_repo=audit_repo,
    )

    assert patient.created_at.tzinfo is not None
