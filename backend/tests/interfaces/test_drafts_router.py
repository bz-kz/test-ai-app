"""カルテ下書きエンドポイントのルーターテスト。

TestClient + インメモリ SQLite + FakeLocalLLMClient を使い、Postgres・LLM なしで実行できる。

BE-006 Acceptance:
  (a) POST /encounters/{id}/drafts 201 — 正常生成
  (b) POST 存在しない encounter_id → 404 code="encounter_not_found" (UUID 非エコー)
  (c) POST clinical_input が空文字 → 422 code="validation_error"
  (d) POST FakeLLM が InferenceError → 503 code="inference_unavailable"; PHI 非エコー
  (e) GET /drafts/{id} 200 — 存在する下書き
  (f) GET /drafts/{id} 404 code="draft_not_found" (UUID 非エコー)
  (g) レスポンスに clinical_input が含まれない

BE-007 Acceptance (PATCH / finalize):
  (h) PATCH /drafts/{id} 200 — 正常編集
  (i) PATCH 存在しない draft_id → 404 code="draft_not_found" (UUID 非エコー)
  (j) PATCH content が空文字 → 422; extra フィールド → 422
  (k) POST /drafts/{id}/finalize 201 — 正常確定
  (l) POST finalize 2 回目 → 409 code="encounter_already_finalized" (PHI/UUID 非エコー)
  (m) POST finalize 存在しない draft_id → 404 code="draft_not_found"
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from uuid import uuid4

import httpx
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
from app.interfaces.auth import get_current_clinician
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
    make_create_encounter,
    make_create_patient,
    make_edit_record_draft,
    make_finalize_draft_to_record_final,
    make_find_draft_by_id,
    make_find_encounter_by_id,
    make_find_final_by_id,
    make_find_patient_by_id,
    make_find_patient_by_mrn,
    make_generate_record_draft,
    make_list_encounters_by_patient,
)
from app.usecases.draft import edit_record_draft, find_draft_by_id, generate_record_draft
from app.usecases.encounter import (
    create_encounter,
    find_encounter_by_id,
    list_encounters_by_patient,
)
from app.usecases.final import finalize_draft_to_record_final, find_final_by_id
from app.usecases.patient import create_patient, find_patient_by_id, find_patient_by_mrn
from tests.conftest import TEST_CLINICIAN_ID

# ---------------------------------------------------------------------------
# テスト用アプリとインメモリ DB のセットアップ
# ---------------------------------------------------------------------------


def _make_test_app(session: AsyncSession, llm: FakeLocalLLMClient) -> FastAPI:
    """インメモリ DB セッションと FakeLLM をユースケースファクトリ DI に差し込んだ
    テスト用 FastAPI を生成する。"""

    # 下書き生成ファクトリの override
    def _override_make_generate_record_draft():  # type: ignore[no-untyped-def]
        encounter_repo = EncounterRepository(session)
        draft_repo = RecordDraftRepository(session)
        audit_repo = AuditLogRepository(session)

        async def _generate(clinical_input, encounter_id, clinician_id):  # type: ignore[no-untyped-def]
            draft = await generate_record_draft(
                clinical_input=clinical_input,
                encounter_id=encounter_id,
                clinician_id=clinician_id,
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

    # 受診ファクトリの override
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

    # 患者ファクトリの override
    def _override_make_create_patient():  # type: ignore[no-untyped-def]
        patient_repo = PatientRepository(session)
        audit_repo = AuditLogRepository(session)

        async def _create(mrn, family_name, given_name, date_of_birth, clinician_id):  # type: ignore[no-untyped-def]
            patient = await create_patient(
                mrn=mrn,
                family_name=family_name,
                given_name=given_name,
                date_of_birth=date_of_birth,
                clinician_id=clinician_id,
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
    # InferenceError は Exception より先に登録する
    test_app.add_exception_handler(InferenceError, inference_error_handler)  # type: ignore[arg-type]
    test_app.add_exception_handler(Exception, unhandled_exception_handler)
    test_app.include_router(patients_router, prefix="")
    test_app.include_router(encounters_router, prefix="")
    test_app.include_router(drafts_router, prefix="")
    test_app.include_router(finals_router, prefix="")

    # DI オーバーライド
    test_app.dependency_overrides[make_generate_record_draft] = _override_make_generate_record_draft
    test_app.dependency_overrides[make_find_draft_by_id] = _override_make_find_draft_by_id
    test_app.dependency_overrides[make_edit_record_draft] = _override_make_edit_record_draft
    test_app.dependency_overrides[make_finalize_draft_to_record_final] = (
        _override_make_finalize_draft_to_record_final
    )
    test_app.dependency_overrides[make_find_final_by_id] = _override_make_find_final_by_id
    test_app.dependency_overrides[make_create_encounter] = _override_make_create_encounter
    test_app.dependency_overrides[make_find_encounter_by_id] = _override_make_find_encounter_by_id
    test_app.dependency_overrides[make_list_encounters_by_patient] = (
        _override_make_list_encounters_by_patient
    )
    test_app.dependency_overrides[make_create_patient] = _override_make_create_patient
    test_app.dependency_overrides[make_find_patient_by_id] = _override_make_find_patient_by_id
    test_app.dependency_overrides[make_find_patient_by_mrn] = _override_make_find_patient_by_mrn
    # get_llm_client は make_generate_record_draft の内部でのみ使われるが念のため override する
    test_app.dependency_overrides[get_llm_client] = lambda: llm
    # BE-012: テスト用固定臨床医 UUID を返すように auth 依存を上書きする
    test_app.dependency_overrides[get_current_clinician] = lambda: TEST_CLINICIAN_ID

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
    """テスト用クライアント (正常系 LLM)。"""
    app = _make_test_app(session, fake_llm)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def error_llm() -> FakeLocalLLMClient:
    """InferenceError を強制する FakeLocalLLMClient。"""
    return FakeLocalLLMClient(force_error=True)


@pytest.fixture()
def error_client(session: AsyncSession, error_llm: FakeLocalLLMClient) -> TestClient:
    """テスト用クライアント (LLM エラー強制)。"""
    app = _make_test_app(session, error_llm)
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# ヘルパー: 患者・受診を作成する
# ---------------------------------------------------------------------------


def _create_patient(client: TestClient, mrn: str = "MRN-DRAFT-R-001") -> httpx.Response:
    return client.post(
        "/patients",
        json={
            "mrn": mrn,
            "family_name": "佐藤",
            "given_name": "一郎",
            "date_of_birth": "1970-03-20",
        },
    )


def _create_encounter(client: TestClient, patient_id: str) -> httpx.Response:
    return client.post(
        "/encounters",
        json={
            "patient_id": patient_id,
            "encountered_at": "2024-06-01T10:00:00Z",
        },
    )


# ---------------------------------------------------------------------------
# (a) POST /encounters/{id}/drafts 201 — 正常生成
# ---------------------------------------------------------------------------


class TestPostDraft:
    def test_201_on_generate(self, client: TestClient) -> None:
        """正常な下書き生成で 201 と DraftRead を返す。"""
        patient_id = _create_patient(client).json()["id"]
        encounter_id = _create_encounter(client, patient_id).json()["id"]

        resp = client.post(
            f"/encounters/{encounter_id}/drafts",
            json={"clinical_input": "38℃の発熱が3日間続いている。"},
        )

        assert resp.status_code == 201
        body = resp.json()
        assert body["encounter_id"] == encounter_id
        assert "id" in body
        assert "content" in body
        assert "created_at" in body
        assert "updated_at" in body

    def test_response_has_draft_read_fields(self, client: TestClient) -> None:
        """DraftRead の宣言フィールドのみがレスポンスに含まれる。"""
        patient_id = _create_patient(client, mrn="MRN-DRAFT-R-002").json()["id"]
        encounter_id = _create_encounter(client, patient_id).json()["id"]

        resp = client.post(
            f"/encounters/{encounter_id}/drafts",
            json={"clinical_input": "胸痛。"},
        )

        assert resp.status_code == 201
        expected = {"id", "encounter_id", "content", "confidence", "created_at", "updated_at"}
        assert set(resp.json().keys()) == expected

    # -------------------------------------------------------------------------
    # (g) レスポンスに clinical_input が含まれない
    # -------------------------------------------------------------------------

    def test_clinical_input_not_echoed_in_response(self, client: TestClient) -> None:
        """レスポンスボディに clinical_input が含まれない。"""
        patient_id = _create_patient(client, mrn="MRN-DRAFT-R-003").json()["id"]
        encounter_id = _create_encounter(client, patient_id).json()["id"]
        clinical_input = "UNIQUE_PHI_MARKER_XYZ_12345"

        resp = client.post(
            f"/encounters/{encounter_id}/drafts",
            json={"clinical_input": clinical_input},
        )

        assert resp.status_code == 201
        # clinical_input はレスポンスのキーに含まれない
        assert "clinical_input" not in resp.json()

    # -------------------------------------------------------------------------
    # (b) 存在しない encounter_id → 404 code="encounter_not_found"
    # -------------------------------------------------------------------------

    def test_404_on_nonexistent_encounter(self, client: TestClient) -> None:
        """存在しない encounter_id で 404 を返す。"""
        resp = client.post(
            f"/encounters/{uuid4()}/drafts",
            json={"clinical_input": "テスト入力"},
        )

        assert resp.status_code == 404
        body = resp.json()
        assert body["code"] == "encounter_not_found"

    def test_404_message_does_not_echo_uuid(self, client: TestClient) -> None:
        """404 エラーメッセージに encounter_id が含まれない (PHI ルール)。"""
        missing_id = str(uuid4())
        resp = client.post(
            f"/encounters/{missing_id}/drafts",
            json={"clinical_input": "テスト入力"},
        )

        assert resp.status_code == 404
        body = resp.json()
        assert missing_id not in body.get("message", "")

    # -------------------------------------------------------------------------
    # (c) clinical_input が空文字 → 422
    # -------------------------------------------------------------------------

    def test_422_on_empty_clinical_input(self, client: TestClient) -> None:
        """clinical_input が空文字で 422 を返す (Field min_length=1)。"""
        patient_id = _create_patient(client, mrn="MRN-DRAFT-R-004").json()["id"]
        encounter_id = _create_encounter(client, patient_id).json()["id"]

        resp = client.post(
            f"/encounters/{encounter_id}/drafts",
            json={"clinical_input": ""},
        )

        assert resp.status_code == 422
        body = resp.json()
        assert body["code"] == "validation_error"

    def test_422_on_extra_field(self, client: TestClient) -> None:
        """extra='forbid' により余分フィールドで 422 を返す。"""
        patient_id = _create_patient(client, mrn="MRN-DRAFT-R-005").json()["id"]
        encounter_id = _create_encounter(client, patient_id).json()["id"]

        resp = client.post(
            f"/encounters/{encounter_id}/drafts",
            json={"clinical_input": "テスト", "unexpected_field": "value"},
        )

        assert resp.status_code == 422

    # -------------------------------------------------------------------------
    # (d) FakeLLM が InferenceError → 503; PHI 非エコー
    # -------------------------------------------------------------------------

    def test_503_on_inference_error(
        self,
        session: AsyncSession,
        error_llm: FakeLocalLLMClient,
        error_client: TestClient,
    ) -> None:
        """FakeLLM が InferenceError を raise すると 503 を返す。"""
        patient_id = _create_patient(error_client, mrn="MRN-DRAFT-R-006").json()["id"]
        encounter_id = _create_encounter(error_client, patient_id).json()["id"]

        resp = error_client.post(
            f"/encounters/{encounter_id}/drafts",
            json={"clinical_input": "腹痛と下痢。"},
        )

        assert resp.status_code == 503
        body = resp.json()
        assert body["code"] == "inference_unavailable"

    def test_503_body_does_not_contain_clinical_input(
        self,
        error_client: TestClient,
    ) -> None:
        """503 レスポンスボディに clinical_input が含まれない。"""
        patient_id = _create_patient(error_client, mrn="MRN-DRAFT-R-007").json()["id"]
        encounter_id = _create_encounter(error_client, patient_id).json()["id"]
        clinical_input = "SENSITIVE_PHI_CONTENT_ABC_9999"

        resp = error_client.post(
            f"/encounters/{encounter_id}/drafts",
            json={"clinical_input": clinical_input},
        )

        assert resp.status_code == 503
        # レスポンスボディに clinical_input が含まれないことを確認する
        assert clinical_input not in resp.text


# ---------------------------------------------------------------------------
# (e) GET /drafts/{id} 200 / (f) 404
# ---------------------------------------------------------------------------


class TestGetDraftById:
    def test_200_on_existing_draft(self, client: TestClient) -> None:
        """GET /drafts/{id} が存在する下書きを返す。"""
        patient_id = _create_patient(client, mrn="MRN-DRAFT-R-010").json()["id"]
        encounter_id = _create_encounter(client, patient_id).json()["id"]

        draft_id = client.post(
            f"/encounters/{encounter_id}/drafts",
            json={"clinical_input": "倦怠感"},
        ).json()["id"]

        resp = client.get(f"/drafts/{draft_id}")

        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == draft_id
        assert body["encounter_id"] == encounter_id

    def test_404_on_nonexistent_draft(self, client: TestClient) -> None:
        """GET /drafts/{id} が存在しない ID で 404 を返す。"""
        resp = client.get(f"/drafts/{uuid4()}")

        assert resp.status_code == 404
        body = resp.json()
        assert body["code"] == "draft_not_found"

    def test_404_message_does_not_echo_uuid(self, client: TestClient) -> None:
        """404 エラーメッセージに draft_id が含まれない (PHI ルール)。"""
        missing_id = str(uuid4())
        resp = client.get(f"/drafts/{missing_id}")

        assert resp.status_code == 404
        body = resp.json()
        assert missing_id not in body.get("message", "")

    def test_response_fields_complete(self, client: TestClient) -> None:
        """DraftRead の全フィールドが返される。"""
        patient_id = _create_patient(client, mrn="MRN-DRAFT-R-011").json()["id"]
        encounter_id = _create_encounter(client, patient_id).json()["id"]

        draft_id = client.post(
            f"/encounters/{encounter_id}/drafts",
            json={"clinical_input": "咳と鼻水"},
        ).json()["id"]

        resp = client.get(f"/drafts/{draft_id}")

        expected = {"id", "encounter_id", "content", "confidence", "created_at", "updated_at"}
        assert set(resp.json().keys()) == expected


# ---------------------------------------------------------------------------
# (h) PATCH /drafts/{id} — 正常編集
# ---------------------------------------------------------------------------


class TestPatchDraft:
    def test_200_on_valid_edit(self, client: TestClient) -> None:
        """PATCH /drafts/{id} が 200 と更新済み DraftRead を返す。"""
        patient_id = _create_patient(client, mrn="MRN-DRAFT-P-001").json()["id"]
        encounter_id = _create_encounter(client, patient_id).json()["id"]
        draft_id = client.post(
            f"/encounters/{encounter_id}/drafts",
            json={"clinical_input": "初期入力"},
        ).json()["id"]

        resp = client.patch(
            f"/drafts/{draft_id}",
            json={"content": "編集後の内容"},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == draft_id
        assert body["content"] == "編集後の内容"

    def test_response_has_draft_read_fields(self, client: TestClient) -> None:
        """PATCH レスポンスが DraftRead の全フィールドを持つ。"""
        patient_id = _create_patient(client, mrn="MRN-DRAFT-P-002").json()["id"]
        encounter_id = _create_encounter(client, patient_id).json()["id"]
        draft_id = client.post(
            f"/encounters/{encounter_id}/drafts",
            json={"clinical_input": "初期入力2"},
        ).json()["id"]

        resp = client.patch(
            f"/drafts/{draft_id}",
            json={"content": "編集後の内容2"},
        )

        assert resp.status_code == 200
        expected = {"id", "encounter_id", "content", "confidence", "created_at", "updated_at"}
        assert set(resp.json().keys()) == expected

    # -------------------------------------------------------------------------
    # (i) PATCH 存在しない draft_id → 404
    # -------------------------------------------------------------------------

    def test_404_on_nonexistent_draft(self, client: TestClient) -> None:
        """PATCH /drafts/{id} が存在しない ID で 404 を返す。"""
        resp = client.patch(
            f"/drafts/{uuid4()}",
            json={"content": "内容"},
        )

        assert resp.status_code == 404
        body = resp.json()
        assert body["code"] == "draft_not_found"

    def test_404_message_does_not_echo_uuid(self, client: TestClient) -> None:
        """404 エラーメッセージに draft_id が含まれない (PHI ルール)。"""
        missing_id = str(uuid4())
        resp = client.patch(
            f"/drafts/{missing_id}",
            json={"content": "内容"},
        )

        assert resp.status_code == 404
        body = resp.json()
        assert missing_id not in body.get("message", "")

    # -------------------------------------------------------------------------
    # (j) PATCH バリデーションエラー
    # -------------------------------------------------------------------------

    def test_422_on_empty_content(self, client: TestClient) -> None:
        """PATCH content が空文字で 422 を返す (Field min_length=1)。"""
        patient_id = _create_patient(client, mrn="MRN-DRAFT-P-003").json()["id"]
        encounter_id = _create_encounter(client, patient_id).json()["id"]
        draft_id = client.post(
            f"/encounters/{encounter_id}/drafts",
            json={"clinical_input": "初期入力3"},
        ).json()["id"]

        resp = client.patch(
            f"/drafts/{draft_id}",
            json={"content": ""},
        )

        assert resp.status_code == 422
        assert resp.json()["code"] == "validation_error"

    def test_422_on_clinician_id_in_body(self, client: TestClient) -> None:
        """clinician_id をボディに含めると 422 を返す (extra='forbid')。BE-012 回帰テスト。"""
        patient_id = _create_patient(client, mrn="MRN-DRAFT-P-004").json()["id"]
        encounter_id = _create_encounter(client, patient_id).json()["id"]
        draft_id = client.post(
            f"/encounters/{encounter_id}/drafts",
            json={"clinical_input": "初期入力4"},
        ).json()["id"]

        resp = client.patch(
            f"/drafts/{draft_id}",
            json={"content": "内容", "clinician_id": str(uuid4())},
        )

        assert resp.status_code == 422

    def test_422_on_extra_field(self, client: TestClient) -> None:
        """extra='forbid' により余分フィールドで 422 を返す。"""
        patient_id = _create_patient(client, mrn="MRN-DRAFT-P-005").json()["id"]
        encounter_id = _create_encounter(client, patient_id).json()["id"]
        draft_id = client.post(
            f"/encounters/{encounter_id}/drafts",
            json={"clinical_input": "初期入力5"},
        ).json()["id"]

        resp = client.patch(
            f"/drafts/{draft_id}",
            json={"content": "内容", "unexpected": "x"},
        )

        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# (k) POST /drafts/{id}/finalize — 正常確定
# ---------------------------------------------------------------------------


class TestFinalizeDraft:
    def test_201_on_finalize(self, client: TestClient) -> None:
        """POST /drafts/{id}/finalize が 201 と FinalRead を返す。"""
        from tests.conftest import TEST_CLINICIAN_ID_STR

        patient_id = _create_patient(client, mrn="MRN-FINAL-R-001").json()["id"]
        encounter_id = _create_encounter(client, patient_id).json()["id"]
        draft_id = client.post(
            f"/encounters/{encounter_id}/drafts",
            json={"clinical_input": "確定テスト入力"},
        ).json()["id"]

        resp = client.post(
            f"/drafts/{draft_id}/finalize",
            json={},
        )

        assert resp.status_code == 201
        body = resp.json()
        assert body["encounter_id"] == encounter_id
        # clinician_id はヘッダーから注入される (テスト用固定 UUID)
        assert body["clinician_id"] == TEST_CLINICIAN_ID_STR
        assert body["predecessor_id"] is None
        assert "id" in body
        assert "content" in body
        assert "created_at" in body

    def test_response_has_final_read_fields(self, client: TestClient) -> None:
        """確定レスポンスが FinalRead の全フィールドを持つ。"""
        patient_id = _create_patient(client, mrn="MRN-FINAL-R-002").json()["id"]
        encounter_id = _create_encounter(client, patient_id).json()["id"]
        draft_id = client.post(
            f"/encounters/{encounter_id}/drafts",
            json={"clinical_input": "確定テスト入力2"},
        ).json()["id"]

        resp = client.post(
            f"/drafts/{draft_id}/finalize",
            json={},
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

    def test_422_on_clinician_id_in_body(self, client: TestClient) -> None:
        """clinician_id をボディに含めると 422 を返す (extra='forbid')。BE-012 回帰テスト。"""
        patient_id = _create_patient(client, mrn="MRN-FINAL-R-022").json()["id"]
        encounter_id = _create_encounter(client, patient_id).json()["id"]
        draft_id = client.post(
            f"/encounters/{encounter_id}/drafts",
            json={"clinical_input": "確定テスト入力022"},
        ).json()["id"]

        resp = client.post(
            f"/drafts/{draft_id}/finalize",
            json={"clinician_id": str(uuid4())},
        )

        assert resp.status_code == 422
        body = resp.json()
        assert body["code"] == "validation_error"

    # -------------------------------------------------------------------------
    # (l) POST finalize 2 回目 → 409
    # -------------------------------------------------------------------------

    def test_409_on_double_finalize(self, client: TestClient) -> None:
        """同一受診で 2 回確定しようとすると 409 を返す。"""
        patient_id = _create_patient(client, mrn="MRN-FINAL-R-003").json()["id"]
        encounter_id = _create_encounter(client, patient_id).json()["id"]
        draft_id = client.post(
            f"/encounters/{encounter_id}/drafts",
            json={"clinical_input": "二重確定テスト"},
        ).json()["id"]

        client.post(f"/drafts/{draft_id}/finalize", json={})

        # 2 回目の確定
        resp2 = client.post(
            f"/drafts/{draft_id}/finalize",
            json={},
        )

        assert resp2.status_code == 409
        body = resp2.json()
        assert body["code"] == "encounter_already_finalized"

    def test_409_message_does_not_echo_phi(self, client: TestClient) -> None:
        """409 エラーメッセージに UUID・PHI が含まれない。"""
        patient_id = _create_patient(client, mrn="MRN-FINAL-R-004").json()["id"]
        encounter_id = _create_encounter(client, patient_id).json()["id"]
        draft_id = client.post(
            f"/encounters/{encounter_id}/drafts",
            json={"clinical_input": "SENSITIVE_PHI_409_TEST"},
        ).json()["id"]

        client.post(f"/drafts/{draft_id}/finalize", json={})
        resp2 = client.post(
            f"/drafts/{draft_id}/finalize",
            json={},
        )

        assert resp2.status_code == 409
        body = resp2.json()
        # UUID や PHI テキストがメッセージに含まれない
        assert draft_id not in body.get("message", "")
        assert encounter_id not in body.get("message", "")
        assert "SENSITIVE_PHI_409_TEST" not in body.get("message", "")

    # -------------------------------------------------------------------------
    # (m) POST finalize 存在しない draft_id → 404
    # -------------------------------------------------------------------------

    def test_404_on_nonexistent_draft(self, client: TestClient) -> None:
        """存在しない draft_id で 404 を返す。"""
        resp = client.post(
            f"/drafts/{uuid4()}/finalize",
            json={},
        )

        assert resp.status_code == 404
        body = resp.json()
        assert body["code"] == "draft_not_found"
