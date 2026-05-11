"""リポジトリ CRUD とチェーン取得のユニットテスト。

SQLite インメモリ DB を使う。Postgres なしで実行できる。
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.domain.entities import (
    AuditAction,
    AuditLog,
    Encounter,
    Patient,
    RecordDraft,
    RecordFinal,
)
from app.infrastructure.db.engine import Base
from app.infrastructure.db.repositories import (
    AuditLogRepository,
    EncounterRepository,
    PatientRepository,
    RecordDraftRepository,
    RecordFinalRepository,
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


def _now() -> datetime:
    return datetime.now(tz=UTC)


# ---------------------------------------------------------------------------
# PatientRepository
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patient_add_and_find_by_id(session: AsyncSession) -> None:
    repo = PatientRepository(session)
    p = Patient(
        id=uuid4(),
        mrn="MRN001",
        family_name="山田",
        given_name="太郎",
        date_of_birth=datetime(1980, 1, 1, tzinfo=UTC),
        created_at=_now(),
    )
    await repo.add(p)
    await session.flush()

    found = await repo.find_by_id(p.id)
    assert found is not None
    assert found.id == p.id
    assert found.mrn == "MRN001"


@pytest.mark.asyncio
async def test_patient_find_by_mrn(session: AsyncSession) -> None:
    repo = PatientRepository(session)
    p = Patient(
        id=uuid4(),
        mrn="MRN999",
        family_name="鈴木",
        given_name="花子",
        date_of_birth=datetime(1990, 6, 15, tzinfo=UTC),
        created_at=_now(),
    )
    await repo.add(p)
    await session.flush()

    found = await repo.find_by_mrn("MRN999")
    assert found is not None
    assert found.id == p.id

    not_found = await repo.find_by_mrn("NONEXISTENT")
    assert not_found is None


# ---------------------------------------------------------------------------
# EncounterRepository
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_encounter_add_and_list_by_patient(session: AsyncSession) -> None:
    p_repo = PatientRepository(session)
    e_repo = EncounterRepository(session)

    patient = Patient(
        id=uuid4(),
        mrn="MRN002",
        family_name="佐藤",
        given_name="一郎",
        date_of_birth=datetime(1975, 3, 20, tzinfo=UTC),
        created_at=_now(),
    )
    await p_repo.add(patient)

    enc = Encounter(
        id=uuid4(),
        patient_id=patient.id,
        encountered_at=_now(),
        clinician_id=uuid4(),
        created_at=_now(),
    )
    await e_repo.add(enc)
    await session.flush()

    encounters = await e_repo.list_by_patient(patient.id)
    assert len(encounters) == 1
    assert encounters[0].id == enc.id


# ---------------------------------------------------------------------------
# RecordDraftRepository
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_draft_add_update_find(session: AsyncSession) -> None:
    p_repo = PatientRepository(session)
    e_repo = EncounterRepository(session)
    d_repo = RecordDraftRepository(session)

    patient = Patient(
        id=uuid4(),
        mrn="MRN003",
        family_name="田中",
        given_name="美穂",
        date_of_birth=datetime(2000, 12, 5, tzinfo=UTC),
        created_at=_now(),
    )
    await p_repo.add(patient)
    enc = Encounter(
        id=uuid4(),
        patient_id=patient.id,
        encountered_at=_now(),
        clinician_id=uuid4(),
        created_at=_now(),
    )
    await e_repo.add(enc)

    draft = RecordDraft(
        id=uuid4(),
        encounter_id=enc.id,
        content="initial draft content",
        confidence=0.85,
        created_at=_now(),
        updated_at=_now(),
    )
    await d_repo.add(draft)
    await session.flush()

    now2 = _now()
    await d_repo.update_content(draft.id, "updated draft content", now2)
    await session.flush()

    found = await d_repo.find_by_id(draft.id)
    assert found is not None
    assert found.content == "updated draft content"


# ---------------------------------------------------------------------------
# RecordFinalRepository - find_chain
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_final_find_chain(session: AsyncSession) -> None:
    """find_chain が predecessor_id チェーンを全て返すことを確認する。"""
    p_repo = PatientRepository(session)
    e_repo = EncounterRepository(session)
    f_repo = RecordFinalRepository(session)

    patient = Patient(
        id=uuid4(),
        mrn="MRN004",
        family_name="高橋",
        given_name="誠",
        date_of_birth=datetime(1965, 8, 8, tzinfo=UTC),
        created_at=_now(),
    )
    await p_repo.add(patient)
    enc = Encounter(
        id=uuid4(),
        patient_id=patient.id,
        encountered_at=_now(),
        clinician_id=uuid4(),
        created_at=_now(),
    )
    await e_repo.add(enc)

    clinician_id = uuid4()
    original = RecordFinal(
        id=uuid4(),
        encounter_id=enc.id,
        content="original",
        confidence=None,
        clinician_id=clinician_id,
        predecessor_id=None,
        created_at=_now(),
    )
    await f_repo.add(original)
    await session.flush()

    correction = RecordFinal(
        id=uuid4(),
        encounter_id=enc.id,
        content="correction",
        confidence=None,
        clinician_id=clinician_id,
        predecessor_id=original.id,
        created_at=_now(),
    )
    await f_repo.add(correction)
    await session.flush()

    chain = await f_repo.find_chain(correction.id)
    assert len(chain) == 2
    assert chain[0].id == original.id
    assert chain[1].id == correction.id


# ---------------------------------------------------------------------------
# AuditLogRepository
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_audit_log_append_and_list(session: AsyncSession) -> None:
    repo = AuditLogRepository(session)

    target_id = uuid4()
    entry = AuditLog(
        id=uuid4(),
        at=_now(),
        actor=uuid4(),
        action=AuditAction.FINAL_CREATE,
        target_kind="record_final",
        target_id=target_id,
        meta_json="{}",
    )
    await repo.append(entry)
    await session.flush()

    logs = await repo.list_by_target("record_final", target_id)
    assert len(logs) == 1
    assert logs[0].action == AuditAction.FINAL_CREATE
    assert logs[0].target_id == target_id
