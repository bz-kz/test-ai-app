"""確定カルテユースケースのユニットテスト (BE-007)。

インメモリ SQLite を使い、Postgres なしで実行できる。

Acceptance:
  (a) finalize_draft_to_record_final — 正常系: RecordFinal を返す;
      predecessor_id=None; FINAL_CREATE 監査 1 件
  (b) finalize_draft_to_record_final — draft 不在 → DraftNotFound; 確定行・監査行なし
  (c) finalize_draft_to_record_final — 二重確定 → EncounterAlreadyFinalized;
      2 件目の確定行なし; 監査行なし
  (d) find_final_by_id ヒット / ミス
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.domain.entities import AuditAction, Encounter
from app.infrastructure.db.engine import Base
from app.infrastructure.db.repositories import (
    AuditLogRepository,
    EncounterRepository,
    PatientRepository,
    RecordDraftRepository,
    RecordFinalRepository,
)
from app.infrastructure.llm.fake_client import FakeLocalLLMClient
from app.usecases.draft import generate_record_draft
from app.usecases.encounter import create_encounter
from app.usecases.errors import DraftNotFound, EncounterAlreadyFinalized, FinalNotFound
from app.usecases.final import finalize_draft_to_record_final, find_final_by_id
from app.usecases.patient import create_patient


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


async def _insert_encounter(session: AsyncSession) -> Encounter:
    """テスト用患者 + 受診を DB に追加するヘルパー。"""
    patient_repo = PatientRepository(session)
    encounter_repo = EncounterRepository(session)
    audit_repo = AuditLogRepository(session)

    patient = await create_patient(
        mrn=f"MRN-FINAL-{uuid4().hex[:8]}",
        family_name="山田",
        given_name="太郎",
        date_of_birth=date(1980, 1, 15),
        patient_repo=patient_repo,
        audit_repo=audit_repo,
    )
    await session.flush()

    encounter = await create_encounter(
        patient_id=patient.id,
        encountered_at=datetime(2024, 7, 1, 9, 0, tzinfo=UTC),
        clinician_id=uuid4(),
        patient_repo=patient_repo,
        encounter_repo=encounter_repo,
        audit_repo=audit_repo,
    )
    await session.flush()
    return encounter


async def _insert_draft(session: AsyncSession, encounter: Encounter) -> None:
    """テスト用下書きを DB に追加するヘルパー。"""
    draft_repo = RecordDraftRepository(session)
    audit_repo = AuditLogRepository(session)
    llm = FakeLocalLLMClient()

    await generate_record_draft(
        clinical_input="テスト臨床入力",
        encounter_id=encounter.id,
        llm=llm,
        encounter_repo=EncounterRepository(session),
        draft_repo=draft_repo,
        audit_repo=audit_repo,
    )
    await session.flush()


# ---------------------------------------------------------------------------
# (a) finalize_draft_to_record_final — 正常系
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_finalize_draft_returns_record_final(session: AsyncSession) -> None:
    """finalize_draft_to_record_final が RecordFinal を返す。predecessor_id は None。"""
    encounter = await _insert_encounter(session)
    draft_repo = RecordDraftRepository(session)
    final_repo = RecordFinalRepository(session)
    audit_repo = AuditLogRepository(session)
    llm = FakeLocalLLMClient()

    draft = await generate_record_draft(
        clinical_input="発熱と咳。",
        encounter_id=encounter.id,
        llm=llm,
        encounter_repo=EncounterRepository(session),
        draft_repo=draft_repo,
        audit_repo=audit_repo,
    )
    await session.flush()

    clinician_id = uuid4()
    final = await finalize_draft_to_record_final(
        draft_id=draft.id,
        clinician_id=clinician_id,
        draft_repo=draft_repo,
        final_repo=final_repo,
        audit_repo=audit_repo,
    )
    await session.flush()

    assert final.id is not None
    assert final.encounter_id == encounter.id
    assert final.content == draft.content
    assert final.clinician_id == clinician_id
    # BE-007 では predecessor_id は常に None
    assert final.predecessor_id is None

    # DB から再取得して永続化されていることを確認する
    found = await final_repo.find_by_id(final.id)
    assert found is not None
    assert found.encounter_id == encounter.id


@pytest.mark.asyncio
async def test_finalize_draft_writes_final_create_audit(session: AsyncSession) -> None:
    """finalize_draft_to_record_final が FINAL_CREATE 監査ログを 1 件書く; meta_json="{}"。"""
    encounter = await _insert_encounter(session)
    draft_repo = RecordDraftRepository(session)
    final_repo = RecordFinalRepository(session)
    audit_repo = AuditLogRepository(session)
    llm = FakeLocalLLMClient()

    draft = await generate_record_draft(
        clinical_input="腹痛。",
        encounter_id=encounter.id,
        llm=llm,
        encounter_repo=EncounterRepository(session),
        draft_repo=draft_repo,
        audit_repo=audit_repo,
    )
    await session.flush()

    clinician_id = uuid4()
    final = await finalize_draft_to_record_final(
        draft_id=draft.id,
        clinician_id=clinician_id,
        draft_repo=draft_repo,
        final_repo=final_repo,
        audit_repo=audit_repo,
    )
    await session.flush()

    logs = await audit_repo.list_by_target("record_final", final.id)
    assert len(logs) == 1
    assert logs[0].action == AuditAction.FINAL_CREATE
    assert logs[0].target_kind == "record_final"
    assert logs[0].target_id == final.id
    assert logs[0].actor == clinician_id
    assert logs[0].meta_json == "{}"


@pytest.mark.asyncio
async def test_finalize_draft_findable_by_encounter(session: AsyncSession) -> None:
    """確定後、find_by_encounter が新しい確定カルテを返す。"""
    encounter = await _insert_encounter(session)
    draft_repo = RecordDraftRepository(session)
    final_repo = RecordFinalRepository(session)
    audit_repo = AuditLogRepository(session)
    llm = FakeLocalLLMClient()

    draft = await generate_record_draft(
        clinical_input="倦怠感。",
        encounter_id=encounter.id,
        llm=llm,
        encounter_repo=EncounterRepository(session),
        draft_repo=draft_repo,
        audit_repo=audit_repo,
    )
    await session.flush()

    final = await finalize_draft_to_record_final(
        draft_id=draft.id,
        clinician_id=uuid4(),
        draft_repo=draft_repo,
        final_repo=final_repo,
        audit_repo=audit_repo,
    )
    await session.flush()

    found = await final_repo.find_by_encounter(encounter.id)
    assert found is not None
    assert found.id == final.id


# ---------------------------------------------------------------------------
# (b) finalize_draft_to_record_final — draft 不在
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_finalize_draft_raises_draft_not_found(session: AsyncSession) -> None:
    """存在しない draft_id で DraftNotFound が raise され、確定行・監査行が書かれない。"""
    final_repo = RecordFinalRepository(session)
    audit_repo = AuditLogRepository(session)
    draft_repo = RecordDraftRepository(session)

    nonexistent_draft_id = uuid4()
    with pytest.raises(DraftNotFound):
        await finalize_draft_to_record_final(
            draft_id=nonexistent_draft_id,
            clinician_id=uuid4(),
            draft_repo=draft_repo,
            final_repo=final_repo,
            audit_repo=audit_repo,
        )

    await session.flush()
    # 確定行が書かれていないことを確認する
    found = await final_repo.find_by_id(uuid4())
    assert found is None


# ---------------------------------------------------------------------------
# (c) finalize_draft_to_record_final — 二重確定防止
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_finalize_draft_raises_encounter_already_finalized(session: AsyncSession) -> None:
    """同一受診で 2 回確定しようとすると EncounterAlreadyFinalized が raise される。"""
    encounter = await _insert_encounter(session)
    draft_repo = RecordDraftRepository(session)
    final_repo = RecordFinalRepository(session)
    audit_repo = AuditLogRepository(session)
    llm = FakeLocalLLMClient()

    # 1 件目の下書き生成 + 確定
    draft1 = await generate_record_draft(
        clinical_input="1 回目入力。",
        encounter_id=encounter.id,
        llm=llm,
        encounter_repo=EncounterRepository(session),
        draft_repo=draft_repo,
        audit_repo=audit_repo,
    )
    await session.flush()

    await finalize_draft_to_record_final(
        draft_id=draft1.id,
        clinician_id=uuid4(),
        draft_repo=draft_repo,
        final_repo=final_repo,
        audit_repo=audit_repo,
    )
    await session.flush()

    # 2 件目の下書き生成 (同じ encounter)
    draft2 = await generate_record_draft(
        clinical_input="2 回目入力。",
        encounter_id=encounter.id,
        llm=llm,
        encounter_repo=EncounterRepository(session),
        draft_repo=draft_repo,
        audit_repo=audit_repo,
    )
    await session.flush()

    # 2 回目の確定は拒否される
    with pytest.raises(EncounterAlreadyFinalized):
        await finalize_draft_to_record_final(
            draft_id=draft2.id,
            clinician_id=uuid4(),
            draft_repo=draft_repo,
            final_repo=final_repo,
            audit_repo=audit_repo,
        )

    await session.flush()
    # 確定カルテが 1 件のみであることを確認する
    # find_by_encounter は 1 件目を返す
    existing = await final_repo.find_by_encounter(encounter.id)
    assert existing is not None
    assert existing.encounter_id == encounter.id


# ---------------------------------------------------------------------------
# (d) find_final_by_id ヒット / ミス
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_find_final_by_id_hit(session: AsyncSession) -> None:
    """find_final_by_id が存在する確定カルテを返す。"""
    encounter = await _insert_encounter(session)
    draft_repo = RecordDraftRepository(session)
    final_repo = RecordFinalRepository(session)
    audit_repo = AuditLogRepository(session)
    llm = FakeLocalLLMClient()

    draft = await generate_record_draft(
        clinical_input="皮膚炎。",
        encounter_id=encounter.id,
        llm=llm,
        encounter_repo=EncounterRepository(session),
        draft_repo=draft_repo,
        audit_repo=audit_repo,
    )
    await session.flush()

    final = await finalize_draft_to_record_final(
        draft_id=draft.id,
        clinician_id=uuid4(),
        draft_repo=draft_repo,
        final_repo=final_repo,
        audit_repo=audit_repo,
    )
    await session.flush()

    found = await find_final_by_id(final_id=final.id, final_repo=final_repo)
    assert found.id == final.id
    assert found.encounter_id == encounter.id


@pytest.mark.asyncio
async def test_find_final_by_id_miss(session: AsyncSession) -> None:
    """find_final_by_id が存在しない ID で FinalNotFound を raise する。"""
    final_repo = RecordFinalRepository(session)

    with pytest.raises(FinalNotFound):
        await find_final_by_id(final_id=uuid4(), final_repo=final_repo)
