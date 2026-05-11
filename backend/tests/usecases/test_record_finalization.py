"""finalize_record ユースケースのユニットテスト。

インメモリ SQLite を使い、Postgres なしで実行できる。
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.domain.entities import AuditAction, Encounter, Patient
from app.infrastructure.db.engine import Base
from app.infrastructure.db.repositories import (
    AuditLogRepository,
    EncounterRepository,
    PatientRepository,
    RecordFinalRepository,
)
from app.usecases.record_finalization import finalize_record


@pytest.fixture()
async def session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


@pytest.fixture()
async def encounter(session: AsyncSession) -> Encounter:
    """テスト用患者・受診をセットアップして Encounter を返す。"""
    p_repo = PatientRepository(session)
    e_repo = EncounterRepository(session)

    patient = Patient(
        id=uuid4(),
        mrn="MRN-UC-001",
        family_name="Test",
        given_name="User",
        date_of_birth=datetime(1985, 4, 10, tzinfo=UTC),
        created_at=datetime.now(tz=UTC),
    )
    await p_repo.add(patient)

    enc = Encounter(
        id=uuid4(),
        patient_id=patient.id,
        encountered_at=datetime.now(tz=UTC),
        clinician_id=uuid4(),
        created_at=datetime.now(tz=UTC),
    )
    await e_repo.add(enc)
    await session.flush()
    return enc


@pytest.mark.asyncio
async def test_finalize_record_creates_final_and_audit(
    session: AsyncSession, encounter: Encounter
) -> None:
    """finalize_record が record_final と audit_log を作成することを確認する。"""
    final_repo = RecordFinalRepository(session)
    audit_repo = AuditLogRepository(session)

    record = await finalize_record(
        encounter_id=encounter.id,
        content="診断: 急性上気道炎",
        clinician_id=encounter.clinician_id,
        confidence=0.9,
        predecessor_id=None,
        final_repo=final_repo,
        audit_repo=audit_repo,
    )
    await session.flush()

    found = await final_repo.find_by_id(record.id)
    assert found is not None
    assert found.predecessor_id is None

    logs = await audit_repo.list_by_target("record_final", record.id)
    assert len(logs) == 1
    assert logs[0].action == AuditAction.FINAL_CREATE


@pytest.mark.asyncio
async def test_finalize_record_correction_sets_predecessor(
    session: AsyncSession, encounter: Encounter
) -> None:
    """訂正版 finalize_record が predecessor_id を正しく設定することを確認する。"""
    final_repo = RecordFinalRepository(session)
    audit_repo = AuditLogRepository(session)

    original = await finalize_record(
        encounter_id=encounter.id,
        content="original note",
        clinician_id=encounter.clinician_id,
        confidence=None,
        predecessor_id=None,
        final_repo=final_repo,
        audit_repo=audit_repo,
    )
    await session.flush()

    correction = await finalize_record(
        encounter_id=encounter.id,
        content="corrected note",
        clinician_id=encounter.clinician_id,
        confidence=None,
        predecessor_id=original.id,
        final_repo=final_repo,
        audit_repo=audit_repo,
    )
    await session.flush()

    assert correction.predecessor_id == original.id

    logs = await audit_repo.list_by_target("record_final", correction.id)
    assert logs[0].action == AuditAction.FINAL_CORRECT
