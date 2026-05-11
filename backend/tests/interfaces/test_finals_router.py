"""確定カルテエンドポイントのルーターテスト (BE-007, BE-008)。

TestClient + インメモリ SQLite + FakeLocalLLMClient を使い、Postgres・LLM なしで実行できる。

Acceptance:
  (a) GET  /finals/{id} 200 — 存在する確定カルテ
  (b) GET  /finals/{id} 404 code="final_not_found" (UUID 非エコー)
  (c) POST /finals/{id}/correct 201 — 正常系
  (d) POST /finals/{id}/correct 404 — 訂正元不在 code="final_not_found" (UUID 非エコー)
  (e) POST /finals/{id}/correct 422 — 空 content / 余分フィールド
  (f) GET  /finals/{id}/chain — 昇順リスト; missing → 404; 順序確認
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.infrastructure.db.engine import Base
from app.infrastructure.db.repositories import (
    AuditLogRepository,
    EncounterRepository,
    PatientRepository,
    RecordDraftRepository,
    RecordFinalRepository,
)
from app.infrastructure.llm.errors import InferenceError
from app.infrastructure.llm.fake_client import FakeLocalLLMClient
from app.interfaces.exception_handlers import (
    http_exception_handler,
    inference_error_handler,
    request_validation_exception_handler,
    unhandled_exception_handler,
)
from app.interfaces.routers.drafts import router as drafts_router
from app.interfaces.routers.encounters import router as encounters_router
from app.interfaces.routers.finals import router as finals_router
from app.interfaces.routers.patients import router as patients_router
from app.usecases.di import (
    get_llm_client,
    make_correct_record_final,
    make_create_encounter,
    make_create_patient,
    make_edit_record_draft,
    make_finalize_draft_to_record_final,
    make_find_chain_for_final,
    make_find_draft_by_id,
    make_find_encounter_by_id,
    make_find_final_by_id,
    make_find_patient_by_id,
    make_find_patient_by_mrn,
    make_generate_record_draft,
    make_list_encounters_by_patient,
    make_list_finals_by_encounter,
)
from app.usecases.draft import edit_record_draft, find_draft_by_id, generate_record_draft
from app.usecases.encounter import (
    create_encounter,
    find_encounter_by_id,
    list_encounters_by_patient,
)
from app.usecases.final import (
    correct_record_final,
    finalize_draft_to_record_final,
    find_chain_for_final,
    find_final_by_id,
    list_finals_by_encounter,
)
from app.usecases.patient import create_patient, find_patient_by_id, find_patient_by_mrn

# ---------------------------------------------------------------------------
# テスト用アプリとインメモリ DB のセットアップ
# ---------------------------------------------------------------------------


def _make_test_app(session: AsyncSession, llm: FakeLocalLLMClient) -> FastAPI:
    """インメモリ DB セッションと FakeLLM をユースケースファクトリ DI に差し込んだ
    テスト用 FastAPI を生成する。"""

    def _override_make_generate_record_draft():  # type: ignore[no-untyped-def]
        encounter_repo = EncounterRepository(session)
        draft_repo = RecordDraftRepository(session)
        audit_repo = AuditLogRepository(session)

        async def _generate(clinical_input, encounter_id):  # type: ignore[no-untyped-def]
            draft = await generate_record_draft(
                clinical_input=clinical_input,
                encounter_id=encounter_id,
                llm=llm,
                encounter_repo=encounter_repo,
                draft_repo=draft_repo,
                audit_repo=audit_repo,
            )
            await session.flush()
            return draft

        return _generate

    def _override_make_find_draft_by_id():  # type: ignore[no-untyped-def]
        draft_repo = RecordDraftRepository(session)

        async def _find(draft_id):  # type: ignore[no-untyped-def]
            return await find_draft_by_id(draft_id=draft_id, draft_repo=draft_repo)

        return _find

    def _override_make_edit_record_draft():  # type: ignore[no-untyped-def]
        draft_repo = RecordDraftRepository(session)
        audit_repo = AuditLogRepository(session)

        async def _edit(draft_id, content, clinician_id):  # type: ignore[no-untyped-def]
            draft = await edit_record_draft(
                draft_id=draft_id,
                content=content,
                clinician_id=clinician_id,
                draft_repo=draft_repo,
                audit_repo=audit_repo,
            )
            await session.flush()
            return draft

        return _edit

    def _override_make_finalize_draft_to_record_final():  # type: ignore[no-untyped-def]
        draft_repo = RecordDraftRepository(session)
        final_repo = RecordFinalRepository(session)
        audit_repo = AuditLogRepository(session)

        async def _finalize(draft_id, clinician_id):  # type: ignore[no-untyped-def]
            final = await finalize_draft_to_record_final(
                draft_id=draft_id,
                clinician_id=clinician_id,
                draft_repo=draft_repo,
                final_repo=final_repo,
                audit_repo=audit_repo,
            )
            await session.flush()
            return final

        return _finalize

    def _override_make_find_final_by_id():  # type: ignore[no-untyped-def]
        final_repo = RecordFinalRepository(session)

        async def _find(final_id):  # type: ignore[no-untyped-def]
            return await find_final_by_id(final_id=final_id, final_repo=final_repo)

        return _find

    def _override_make_correct_record_final():  # type: ignore[no-untyped-def]
        final_repo = RecordFinalRepository(session)
        audit_repo = AuditLogRepository(session)

        async def _correct(source_final_id, content, clinician_id):  # type: ignore[no-untyped-def]
            new_final = await correct_record_final(
                source_final_id=source_final_id,
                content=content,
                clinician_id=clinician_id,
                final_repo=final_repo,
                audit_repo=audit_repo,
            )
            await session.flush()
            return new_final

        return _correct

    def _override_make_list_finals_by_encounter():  # type: ignore[no-untyped-def]
        final_repo = RecordFinalRepository(session)

        async def _list(encounter_id):  # type: ignore[no-untyped-def]
            return await list_finals_by_encounter(
                encounter_id=encounter_id,
                final_repo=final_repo,
            )

        return _list

    def _override_make_find_chain_for_final():  # type: ignore[no-untyped-def]
        final_repo = RecordFinalRepository(session)

        async def _find_chain(final_id):  # type: ignore[no-untyped-def]
            return await find_chain_for_final(final_id=final_id, final_repo=final_repo)

        return _find_chain

    def _override_make_create_encounter():  # type: ignore[no-untyped-def]
        patient_repo = PatientRepository(session)
        encounter_repo = EncounterRepository(session)
        audit_repo = AuditLogRepository(session)

        async def _create(patient_id, encountered_at, clinician_id):  # type: ignore[no-untyped-def]
            encounter = await create_encounter(
                patient_id=patient_id,
                encountered_at=encountered_at,
                clinician_id=clinician_id,
                patient_repo=patient_repo,
                encounter_repo=encounter_repo,
                audit_repo=audit_repo,
            )
            await session.flush()
            return encounter

        return _create

    def _override_make_find_encounter_by_id():  # type: ignore[no-untyped-def]
        encounter_repo = EncounterRepository(session)

        async def _find(encounter_id):  # type: ignore[no-untyped-def]
            return await find_encounter_by_id(
                encounter_id=encounter_id,
                encounter_repo=encounter_repo,
            )

        return _find

    def _override_make_list_encounters_by_patient():  # type: ignore[no-untyped-def]
        patient_repo = PatientRepository(session)
        encounter_repo = EncounterRepository(session)

        async def _list(patient_id):  # type: ignore[no-untyped-def]
            return await list_encounters_by_patient(
                patient_id=patient_id,
                patient_repo=patient_repo,
                encounter_repo=encounter_repo,
            )

        return _list

    def _override_make_create_patient():  # type: ignore[no-untyped-def]
        patient_repo = PatientRepository(session)
        audit_repo = AuditLogRepository(session)

        async def _create(mrn, family_name, given_name, date_of_birth):  # type: ignore[no-untyped-def]
            patient = await create_patient(
                mrn=mrn,
                family_name=family_name,
                given_name=given_name,
                date_of_birth=date_of_birth,
                patient_repo=patient_repo,
                audit_repo=audit_repo,
            )
            await session.flush()
            return patient

        return _create

    def _override_make_find_patient_by_id():  # type: ignore[no-untyped-def]
        patient_repo = PatientRepository(session)

        async def _find(patient_id):  # type: ignore[no-untyped-def]
            return await find_patient_by_id(patient_id=patient_id, patient_repo=patient_repo)

        return _find

    def _override_make_find_patient_by_mrn():  # type: ignore[no-untyped-def]
        patient_repo = PatientRepository(session)

        async def _find(mrn):  # type: ignore[no-untyped-def]
            return await find_patient_by_mrn(mrn=mrn, patient_repo=patient_repo)

        return _find

    test_app = FastAPI()
    test_app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    test_app.add_exception_handler(
        RequestValidationError,
        request_validation_exception_handler,  # type: ignore[arg-type]
    )
    test_app.add_exception_handler(InferenceError, inference_error_handler)  # type: ignore[arg-type]
    test_app.add_exception_handler(Exception, unhandled_exception_handler)
    test_app.include_router(patients_router, prefix="")
    test_app.include_router(encounters_router, prefix="")
    test_app.include_router(drafts_router, prefix="")
    test_app.include_router(finals_router, prefix="")

    test_app.dependency_overrides[make_generate_record_draft] = _override_make_generate_record_draft
    test_app.dependency_overrides[make_find_draft_by_id] = _override_make_find_draft_by_id
    test_app.dependency_overrides[make_edit_record_draft] = _override_make_edit_record_draft
    test_app.dependency_overrides[make_finalize_draft_to_record_final] = (
        _override_make_finalize_draft_to_record_final
    )
    test_app.dependency_overrides[make_find_final_by_id] = _override_make_find_final_by_id
    test_app.dependency_overrides[make_correct_record_final] = _override_make_correct_record_final
    test_app.dependency_overrides[make_list_finals_by_encounter] = (
        _override_make_list_finals_by_encounter
    )
    test_app.dependency_overrides[make_find_chain_for_final] = _override_make_find_chain_for_final
    test_app.dependency_overrides[make_create_encounter] = _override_make_create_encounter
    test_app.dependency_overrides[make_find_encounter_by_id] = _override_make_find_encounter_by_id
    test_app.dependency_overrides[make_list_encounters_by_patient] = (
        _override_make_list_encounters_by_patient
    )
    test_app.dependency_overrides[make_create_patient] = _override_make_create_patient
    test_app.dependency_overrides[make_find_patient_by_id] = _override_make_find_patient_by_id
    test_app.dependency_overrides[make_find_patient_by_mrn] = _override_make_find_patient_by_mrn
    test_app.dependency_overrides[get_llm_client] = lambda: llm

    return test_app


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


@pytest.fixture()
def fake_llm() -> FakeLocalLLMClient:
    """デフォルトの FakeLocalLLMClient。"""
    return FakeLocalLLMClient()


@pytest.fixture()
def client(session: AsyncSession, fake_llm: FakeLocalLLMClient) -> TestClient:
    """テスト用クライアント。"""
    app = _make_test_app(session, fake_llm)
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# ヘルパー: 患者・受診・下書き・確定カルテを作成する
# ---------------------------------------------------------------------------


def _create_patient(client: TestClient, mrn: str = "MRN-FINAL-RT-001") -> str:
    resp = client.post(
        "/patients",
        json={
            "mrn": mrn,
            "family_name": "鈴木",
            "given_name": "三郎",
            "date_of_birth": "1975-08-20",
        },
    )
    return str(resp.json()["id"])


def _create_encounter(client: TestClient, patient_id: str) -> str:
    resp = client.post(
        "/encounters",
        json={
            "patient_id": patient_id,
            "encountered_at": "2024-08-01T10:00:00Z",
            "clinician_id": str(uuid4()),
        },
    )
    return str(resp.json()["id"])


def _create_draft(client: TestClient, encounter_id: str) -> str:
    resp = client.post(
        f"/encounters/{encounter_id}/drafts",
        json={"clinical_input": "ルーターテスト臨床入力"},
    )
    return str(resp.json()["id"])


def _finalize_draft(client: TestClient, draft_id: str) -> str:
    resp = client.post(
        f"/drafts/{draft_id}/finalize",
        json={"clinician_id": str(uuid4())},
    )
    return str(resp.json()["id"])


# ---------------------------------------------------------------------------
# (a) GET /finals/{id} 200
# ---------------------------------------------------------------------------


class TestGetFinalById:
    def test_200_on_existing_final(self, client: TestClient) -> None:
        """GET /finals/{id} が存在する確定カルテを返す。"""
        patient_id = _create_patient(client, "MRN-FINAL-RT-010")
        encounter_id = _create_encounter(client, patient_id)
        draft_id = _create_draft(client, encounter_id)
        final_id = _finalize_draft(client, draft_id)

        resp = client.get(f"/finals/{final_id}")

        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == final_id
        assert body["encounter_id"] == encounter_id

    def test_response_has_final_read_fields(self, client: TestClient) -> None:
        """FinalRead の全フィールドが返される。"""
        patient_id = _create_patient(client, "MRN-FINAL-RT-011")
        encounter_id = _create_encounter(client, patient_id)
        draft_id = _create_draft(client, encounter_id)
        final_id = _finalize_draft(client, draft_id)

        resp = client.get(f"/finals/{final_id}")

        assert resp.status_code == 200
        expected = {
            "id",
            "encounter_id",
            "content",
            "confidence",
            "clinician_id",
            "predecessor_id",
            "created_at",
        }
        assert set(resp.json().keys()) == expected

    # -------------------------------------------------------------------------
    # (b) GET /finals/{id} 404
    # -------------------------------------------------------------------------

    def test_404_on_nonexistent_final(self, client: TestClient) -> None:
        """GET /finals/{id} が存在しない ID で 404 を返す。"""
        resp = client.get(f"/finals/{uuid4()}")

        assert resp.status_code == 404
        body = resp.json()
        assert body["code"] == "final_not_found"

    def test_404_message_does_not_echo_uuid(self, client: TestClient) -> None:
        """404 エラーメッセージに final_id が含まれない (PHI ルール)。"""
        missing_id = str(uuid4())
        resp = client.get(f"/finals/{missing_id}")

        assert resp.status_code == 404
        body = resp.json()
        assert missing_id not in body.get("message", "")


# ---------------------------------------------------------------------------
# (c) POST /finals/{id}/correct 201 — 正常系
# (d) POST /finals/{id}/correct 404 — 訂正元不在
# (e) POST /finals/{id}/correct 422 — バリデーションエラー
# ---------------------------------------------------------------------------


class TestPostCorrectFinal:
    def test_201_happy_path(self, client: TestClient) -> None:
        """POST /finals/{id}/correct が 201 と新しい FinalRead を返す。"""
        patient_id = _create_patient(client, "MRN-CORRECT-001")
        encounter_id = _create_encounter(client, patient_id)
        draft_id = _create_draft(client, encounter_id)
        original_id = _finalize_draft(client, draft_id)

        resp = client.post(
            f"/finals/{original_id}/correct",
            json={"content": "訂正後の内容。", "clinician_id": str(uuid4())},
        )

        assert resp.status_code == 201
        body = resp.json()
        assert body["predecessor_id"] == original_id
        assert body["encounter_id"] == encounter_id
        assert body["confidence"] is None

    def test_201_response_has_all_final_read_fields(self, client: TestClient) -> None:
        """訂正レスポンスが FinalRead の全フィールドを含む。"""
        patient_id = _create_patient(client, "MRN-CORRECT-002")
        encounter_id = _create_encounter(client, patient_id)
        draft_id = _create_draft(client, encounter_id)
        original_id = _finalize_draft(client, draft_id)

        resp = client.post(
            f"/finals/{original_id}/correct",
            json={"content": "訂正後の内容。", "clinician_id": str(uuid4())},
        )

        assert resp.status_code == 201
        expected = {
            "id",
            "encounter_id",
            "content",
            "confidence",
            "clinician_id",
            "predecessor_id",
            "created_at",
        }
        assert set(resp.json().keys()) == expected

    def test_404_on_nonexistent_source(self, client: TestClient) -> None:
        """存在しない source_final_id で 404 code='final_not_found' を返す。"""
        resp = client.post(
            f"/finals/{uuid4()}/correct",
            json={"content": "訂正内容。", "clinician_id": str(uuid4())},
        )

        assert resp.status_code == 404
        body = resp.json()
        assert body["code"] == "final_not_found"

    def test_404_message_does_not_echo_uuid(self, client: TestClient) -> None:
        """404 エラーメッセージに UUID が含まれない (PHI ルール)。"""
        missing_id = str(uuid4())
        resp = client.post(
            f"/finals/{missing_id}/correct",
            json={"content": "訂正内容。", "clinician_id": str(uuid4())},
        )

        assert resp.status_code == 404
        body = resp.json()
        assert missing_id not in body.get("message", "")

    def test_422_on_empty_content(self, client: TestClient) -> None:
        """空 content で 422 バリデーションエラーを返す (min_length=1)。"""
        patient_id = _create_patient(client, "MRN-CORRECT-003")
        encounter_id = _create_encounter(client, patient_id)
        draft_id = _create_draft(client, encounter_id)
        original_id = _finalize_draft(client, draft_id)

        resp = client.post(
            f"/finals/{original_id}/correct",
            json={"content": "", "clinician_id": str(uuid4())},
        )

        assert resp.status_code == 422
        body = resp.json()
        assert body["code"] == "validation_error"

    def test_422_on_extra_field(self, client: TestClient) -> None:
        """余分フィールドで 422 を返す (extra='forbid')。"""
        patient_id = _create_patient(client, "MRN-CORRECT-004")
        encounter_id = _create_encounter(client, patient_id)
        draft_id = _create_draft(client, encounter_id)
        original_id = _finalize_draft(client, draft_id)

        resp = client.post(
            f"/finals/{original_id}/correct",
            json={
                "content": "訂正内容。",
                "clinician_id": str(uuid4()),
                "unexpected_field": "value",
            },
        )

        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# (f) GET /finals/{id}/chain
# ---------------------------------------------------------------------------


class TestGetFinalChain:
    def test_chain_single_element(self, client: TestClient) -> None:
        """predecessor なし確定カルテのチェーンは 1 要素。"""
        patient_id = _create_patient(client, "MRN-CHAIN-001")
        encounter_id = _create_encounter(client, patient_id)
        draft_id = _create_draft(client, encounter_id)
        final_id = _finalize_draft(client, draft_id)

        resp = client.get(f"/finals/{final_id}/chain")

        assert resp.status_code == 200
        chain = resp.json()
        assert len(chain) == 1
        assert chain[0]["id"] == final_id

    def test_chain_ordered_oldest_to_newest(self, client: TestClient) -> None:
        """チェーンが [最古版, ..., 指定版] の昇順で返される。"""
        patient_id = _create_patient(client, "MRN-CHAIN-002")
        encounter_id = _create_encounter(client, patient_id)
        draft_id = _create_draft(client, encounter_id)
        v1_id = _finalize_draft(client, draft_id)

        # v2 = v1 の訂正
        resp_v2 = client.post(
            f"/finals/{v1_id}/correct",
            json={"content": "v2 訂正。", "clinician_id": str(uuid4())},
        )
        assert resp_v2.status_code == 201
        v2_id = resp_v2.json()["id"]

        # v2 のチェーン: [v1, v2]
        resp = client.get(f"/finals/{v2_id}/chain")

        assert resp.status_code == 200
        chain = resp.json()
        assert len(chain) == 2
        assert chain[0]["id"] == v1_id
        assert chain[1]["id"] == v2_id

    def test_404_on_nonexistent_final(self, client: TestClient) -> None:
        """存在しない final_id で 404 code='final_not_found' を返す。"""
        resp = client.get(f"/finals/{uuid4()}/chain")

        assert resp.status_code == 404
        body = resp.json()
        assert body["code"] == "final_not_found"

    def test_404_message_does_not_echo_uuid(self, client: TestClient) -> None:
        """404 エラーメッセージに final_id が含まれない (PHI ルール)。"""
        missing_id = str(uuid4())
        resp = client.get(f"/finals/{missing_id}/chain")

        assert resp.status_code == 404
        body = resp.json()
        assert missing_id not in body.get("message", "")
