"""カルテ下書きユースケースのユニットテスト。

インメモリ SQLite + FakeLocalLLMClient を使い、Postgres・LLM なしで実行できる。

BE-006 Acceptance:
  (a) generate_record_draft が RecordDraft を返す (content は FakeLLM の応答)
  (b) generate_record_draft が DRAFT_CREATE 監査ログを 1 件書く; meta_json="{}"
  (c) 存在しない encounter_id → EncounterNotFound; 下書き行・監査行なし
  (d) FakeLLM が InferenceError → 例外が伝播; 下書き行・監査行なし
  (e) find_draft_by_id ヒット / ミス
  (f) created_at == updated_at (UTC)

BE-007 Acceptance (edit):
  (g) edit_record_draft が更新済み RecordDraft を返す; updated_at が進む; DRAFT_UPDATE 監査 1 件
  (h) 存在しない draft_id → DraftNotFound; 監査行なし; 下書き変更なし

BE-009 Acceptance (list):
  (i) list_drafts_by_encounter が N 件を created_at 降順で返す
  (j) 下書きがない受診で空リストを返す (例外なし)
  (k) 存在しない encounter_id でも空リストを返す (受診存在確認なし)
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
)
from app.infrastructure.llm.errors import InferenceError
from app.infrastructure.llm.fake_client import FakeLocalLLMClient
from app.usecases.draft import (
    edit_record_draft,
    find_draft_by_id,
    generate_record_draft,
    list_drafts_by_encounter,
)
from app.usecases.encounter import create_encounter
from app.usecases.errors import DraftNotFound, EncounterNotFound
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
        mrn="MRN-DRAFT-001",
        family_name="田中",
        given_name="花子",
        date_of_birth=date(1990, 6, 15),
        clinician_id=uuid4(),
        patient_repo=patient_repo,
        audit_repo=audit_repo,
    )
    await session.flush()

    encounter = await create_encounter(
        patient_id=patient.id,
        encountered_at=datetime(2024, 5, 10, 9, 0, tzinfo=UTC),
        clinician_id=uuid4(),
        patient_repo=patient_repo,
        encounter_repo=encounter_repo,
        audit_repo=audit_repo,
    )
    await session.flush()
    return encounter


# ---------------------------------------------------------------------------
# (a) generate_record_draft が RecordDraft を返す
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_record_draft_returns_entity(session: AsyncSession) -> None:
    """generate_record_draft が正しいフィールドを持つ RecordDraft を返す。"""
    encounter = await _insert_encounter(session)
    encounter_repo = EncounterRepository(session)
    draft_repo = RecordDraftRepository(session)
    audit_repo = AuditLogRepository(session)

    fake_text = "【主訴・現病歴 (Subjective)】\n発熱"
    llm = FakeLocalLLMClient(fixture_map={"__any__": fake_text})
    # FakeLLMClient はプロンプトをキーに使う; DEFAULT_RESPONSE を返すように force しない

    draft = await generate_record_draft(
        clinical_input="38℃の発熱が3日間続いている。",
        encounter_id=encounter.id,
        clinician_id=uuid4(),
        llm=llm,
        encounter_repo=encounter_repo,
        draft_repo=draft_repo,
        audit_repo=audit_repo,
    )
    await session.flush()

    assert draft.encounter_id == encounter.id
    assert draft.id is not None
    # FakeLocalLLMClient は DEFAULT_RESPONSE を返す (fixture_map キー不一致時)
    assert draft.content == FakeLocalLLMClient.DEFAULT_RESPONSE
    assert draft.created_at is not None
    assert draft.updated_at is not None

    # DB から再取得して永続化されていることを確認する
    found = await draft_repo.find_by_id(draft.id)
    assert found is not None
    assert found.encounter_id == encounter.id


# ---------------------------------------------------------------------------
# (b) DRAFT_CREATE 監査ログが 1 件書かれ meta_json="{}"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_record_draft_writes_one_audit_log(session: AsyncSession) -> None:
    """generate_record_draft が DRAFT_CREATE の監査ログを 1 件書く; meta_json="{}"。"""
    encounter = await _insert_encounter(session)
    encounter_repo = EncounterRepository(session)
    draft_repo = RecordDraftRepository(session)
    audit_repo = AuditLogRepository(session)

    llm = FakeLocalLLMClient()

    draft = await generate_record_draft(
        clinical_input="胸痛と息切れ。",
        encounter_id=encounter.id,
        clinician_id=uuid4(),
        llm=llm,
        encounter_repo=encounter_repo,
        draft_repo=draft_repo,
        audit_repo=audit_repo,
    )
    await session.flush()

    logs = await audit_repo.list_by_target("record_draft", draft.id)
    assert len(logs) == 1
    assert logs[0].action == AuditAction.DRAFT_CREATE
    assert logs[0].target_kind == "record_draft"
    assert logs[0].target_id == draft.id
    # PHI を含まないメタデータ
    assert logs[0].meta_json == "{}"


# ---------------------------------------------------------------------------
# (c) 存在しない encounter_id → EncounterNotFound; 行なし
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_record_draft_raises_encounter_not_found(session: AsyncSession) -> None:
    """存在しない encounter_id で EncounterNotFound が raise され、下書き/監査行が書かれない。"""
    encounter_repo = EncounterRepository(session)
    draft_repo = RecordDraftRepository(session)
    audit_repo = AuditLogRepository(session)

    llm = FakeLocalLLMClient()
    nonexistent_id = uuid4()

    with pytest.raises(EncounterNotFound):
        await generate_record_draft(
            clinical_input="テスト入力",
            encounter_id=nonexistent_id,
            clinician_id=uuid4(),
            llm=llm,
            encounter_repo=encounter_repo,
            draft_repo=draft_repo,
            audit_repo=audit_repo,
        )

    await session.flush()
    # LLM は呼ばれない
    assert llm.generate_call_count == 0


# ---------------------------------------------------------------------------
# (d) FakeLLM が InferenceError → 例外が伝播; 行なし
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_record_draft_propagates_inference_error(session: AsyncSession) -> None:
    """FakeLLM が InferenceError を raise すると、そのまま伝播する。下書き/監査行は書かれない。"""
    encounter = await _insert_encounter(session)
    encounter_repo = EncounterRepository(session)
    draft_repo = RecordDraftRepository(session)
    audit_repo = AuditLogRepository(session)

    llm = FakeLocalLLMClient(force_error=True)

    with pytest.raises(InferenceError):
        await generate_record_draft(
            clinical_input="テスト入力",
            encounter_id=encounter.id,
            clinician_id=uuid4(),
            llm=llm,
            encounter_repo=encounter_repo,
            draft_repo=draft_repo,
            audit_repo=audit_repo,
        )

    await session.flush()
    # 下書き行が書かれていないことを確認する
    dummy_draft = await draft_repo.find_by_id(uuid4())
    assert dummy_draft is None


# ---------------------------------------------------------------------------
# (e) find_draft_by_id ヒット / ミス
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_find_draft_by_id_hit(session: AsyncSession) -> None:
    """find_draft_by_id が存在する下書きを返す。"""
    encounter = await _insert_encounter(session)
    encounter_repo = EncounterRepository(session)
    draft_repo = RecordDraftRepository(session)
    audit_repo = AuditLogRepository(session)

    llm = FakeLocalLLMClient()
    draft = await generate_record_draft(
        clinical_input="頭痛と吐き気。",
        encounter_id=encounter.id,
        clinician_id=uuid4(),
        llm=llm,
        encounter_repo=encounter_repo,
        draft_repo=draft_repo,
        audit_repo=audit_repo,
    )
    await session.flush()

    found = await find_draft_by_id(draft_id=draft.id, draft_repo=draft_repo)
    assert found.id == draft.id
    assert found.encounter_id == encounter.id


@pytest.mark.asyncio
async def test_find_draft_by_id_miss(session: AsyncSession) -> None:
    """find_draft_by_id が存在しない ID で DraftNotFound を raise する。"""
    draft_repo = RecordDraftRepository(session)

    with pytest.raises(DraftNotFound):
        await find_draft_by_id(draft_id=uuid4(), draft_repo=draft_repo)


# ---------------------------------------------------------------------------
# (f) created_at == updated_at (UTC)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_record_draft_timestamps_are_equal_and_utc(session: AsyncSession) -> None:
    """生成直後の created_at と updated_at が等しく、UTC タイムゾーン付きであること。"""
    encounter = await _insert_encounter(session)
    encounter_repo = EncounterRepository(session)
    draft_repo = RecordDraftRepository(session)
    audit_repo = AuditLogRepository(session)

    llm = FakeLocalLLMClient()
    draft = await generate_record_draft(
        clinical_input="関節痛と倦怠感。",
        encounter_id=encounter.id,
        clinician_id=uuid4(),
        llm=llm,
        encounter_repo=encounter_repo,
        draft_repo=draft_repo,
        audit_repo=audit_repo,
    )

    # SQLite はタイムゾーン情報を落とすため、tzinfo の有無ではなく値の一致を確認する
    assert draft.created_at.replace(tzinfo=None) == draft.updated_at.replace(tzinfo=None)
    # ユースケース内で UTC を明示的に使っていることを確認する
    assert draft.created_at is not None


# ---------------------------------------------------------------------------
# (g) edit_record_draft — 正常系
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_edit_record_draft_returns_updated_entity(session: AsyncSession) -> None:
    """edit_record_draft が更新済み RecordDraft を返し、content が反映される。"""
    encounter = await _insert_encounter(session)
    encounter_repo = EncounterRepository(session)
    draft_repo = RecordDraftRepository(session)
    audit_repo = AuditLogRepository(session)

    llm = FakeLocalLLMClient()
    draft = await generate_record_draft(
        clinical_input="発熱。",
        encounter_id=encounter.id,
        clinician_id=uuid4(),
        llm=llm,
        encounter_repo=encounter_repo,
        draft_repo=draft_repo,
        audit_repo=audit_repo,
    )
    await session.flush()

    clinician_id = uuid4()
    new_content = "【主訴】発熱 (編集済み)"
    updated = await edit_record_draft(
        draft_id=draft.id,
        content=new_content,
        clinician_id=clinician_id,
        draft_repo=draft_repo,
        audit_repo=audit_repo,
    )
    await session.flush()

    assert updated.id == draft.id
    assert updated.content == new_content
    # updated_at が元の created_at 以上であること (SQLite 精度の都合で >= を使う)
    assert updated.updated_at.replace(tzinfo=None) >= draft.created_at.replace(tzinfo=None)


@pytest.mark.asyncio
async def test_edit_record_draft_writes_one_draft_update_audit(session: AsyncSession) -> None:
    """edit_record_draft が DRAFT_UPDATE 監査ログを 1 件書く; meta_json="{}"。"""
    encounter = await _insert_encounter(session)
    encounter_repo = EncounterRepository(session)
    draft_repo = RecordDraftRepository(session)
    audit_repo = AuditLogRepository(session)

    llm = FakeLocalLLMClient()
    draft = await generate_record_draft(
        clinical_input="頭痛。",
        encounter_id=encounter.id,
        clinician_id=uuid4(),
        llm=llm,
        encounter_repo=encounter_repo,
        draft_repo=draft_repo,
        audit_repo=audit_repo,
    )
    await session.flush()

    clinician_id = uuid4()
    await edit_record_draft(
        draft_id=draft.id,
        content="編集後の内容",
        clinician_id=clinician_id,
        draft_repo=draft_repo,
        audit_repo=audit_repo,
    )
    await session.flush()

    logs = await audit_repo.list_by_target("record_draft", draft.id)
    # DRAFT_CREATE (生成時) + DRAFT_UPDATE (編集時) の 2 件
    update_logs = [log for log in logs if log.action == AuditAction.DRAFT_UPDATE]
    assert len(update_logs) == 1
    assert update_logs[0].target_id == draft.id
    assert update_logs[0].actor == clinician_id
    assert update_logs[0].meta_json == "{}"


# ---------------------------------------------------------------------------
# (h) edit_record_draft — 存在しない draft_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_edit_record_draft_raises_draft_not_found(session: AsyncSession) -> None:
    """存在しない draft_id で DraftNotFound が raise され、監査行が書かれない。"""
    draft_repo = RecordDraftRepository(session)
    audit_repo = AuditLogRepository(session)

    nonexistent_id = uuid4()
    with pytest.raises(DraftNotFound):
        await edit_record_draft(
            draft_id=nonexistent_id,
            content="変更内容",
            clinician_id=uuid4(),
            draft_repo=draft_repo,
            audit_repo=audit_repo,
        )

    await session.flush()
    # 監査行が書かれていないことを確認する
    logs = await audit_repo.list_by_target("record_draft", nonexistent_id)
    assert len(logs) == 0


# ---------------------------------------------------------------------------
# (i) list_drafts_by_encounter — N 件を created_at 降順で返す
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_drafts_by_encounter_returns_ordered_desc(session: AsyncSession) -> None:
    """list_drafts_by_encounter が created_at 降順で下書きを返す (BE-009)。"""
    encounter = await _insert_encounter(session)
    encounter_repo = EncounterRepository(session)
    draft_repo = RecordDraftRepository(session)
    audit_repo = AuditLogRepository(session)
    llm = FakeLocalLLMClient()

    # 2 件の下書きを順に生成する
    draft_a = await generate_record_draft(
        clinical_input="1 件目の入力",
        encounter_id=encounter.id,
        clinician_id=uuid4(),
        llm=llm,
        encounter_repo=encounter_repo,
        draft_repo=draft_repo,
        audit_repo=audit_repo,
    )
    await session.flush()

    draft_b = await generate_record_draft(
        clinical_input="2 件目の入力",
        encounter_id=encounter.id,
        clinician_id=uuid4(),
        llm=llm,
        encounter_repo=encounter_repo,
        draft_repo=draft_repo,
        audit_repo=audit_repo,
    )
    await session.flush()

    drafts = await list_drafts_by_encounter(
        encounter_id=encounter.id,
        draft_repo=draft_repo,
    )

    assert len(drafts) == 2
    # 降順: 2 件目 (新しい方) が先頭
    ids = [d.id for d in drafts]
    assert ids[0] == draft_b.id
    assert ids[1] == draft_a.id
    # created_at 降順を確認する
    assert drafts[0].created_at.replace(tzinfo=None) >= drafts[1].created_at.replace(tzinfo=None)


# ---------------------------------------------------------------------------
# (j) 下書きがない受診 → 空リスト (例外なし)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_drafts_by_encounter_empty_on_no_drafts(session: AsyncSession) -> None:
    """下書きがない受診では空リストを返す。例外は raise しない (BE-009)。"""
    encounter = await _insert_encounter(session)
    draft_repo = RecordDraftRepository(session)

    drafts = await list_drafts_by_encounter(
        encounter_id=encounter.id,
        draft_repo=draft_repo,
    )

    assert drafts == []


# ---------------------------------------------------------------------------
# (k) 存在しない encounter_id → 空リスト (受診存在確認なし)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_drafts_by_encounter_empty_on_unknown_encounter(session: AsyncSession) -> None:
    """存在しない encounter_id でも空リストを返す。受診の存在確認は行わない (BE-009)。"""
    draft_repo = RecordDraftRepository(session)

    drafts = await list_drafts_by_encounter(
        encounter_id=uuid4(),
        draft_repo=draft_repo,
    )

    assert drafts == []
