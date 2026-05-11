"""受診エンドポイントのルーターテスト。

TestClient + インメモリ SQLite を使い、Postgres なしで実行できる。
BE-005 Acceptance:
  (a) POST /encounters 201 — 正常作成
  (b) POST /encounters 存在しない patient_id → 404 code="patient_not_found"
  (c) POST /encounters 余分フィールド → 422
  (d) GET  /encounters/{id} 200 — 存在する受診
  (e) GET  /encounters/{id} 404 code="encounter_not_found"
  (f) GET  /patients/{id}/encounters 200 — 空リスト
  (g) GET  /patients/{id}/encounters 200 — 複数、encountered_at 降順
  (h) GET  /patients/{id}/encounters 404 — 存在しない患者
  (i) エラーメッセージに UUID が含まれない
BE-008 Acceptance:
  (j) GET  /encounters/{id}/finals 200 — 空リスト (確定なし)
  (k) GET  /encounters/{id}/finals 200 — シード後に確定リスト返す
  (l) GET  /encounters/{id}/finals 200 — 未知 encounter_id でも 404 ではなく空リスト

DI 方針:
  ルーターはユースケースファクトリ依存を使うため、
  テストでは各ファクトリを override する。infrastructure は直接参照しない。
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
from app.infrastructure.llm.fake_client import FakeLocalLLMClient
from app.interfaces.exception_handlers import (
    http_exception_handler,
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


def _make_test_app(session: AsyncSession, llm: FakeLocalLLMClient | None = None) -> FastAPI:
    """インメモリ DB セッションをユースケースファクトリ DI に差し込んだ
    テスト用 FastAPI を生成する。"""

    _llm = llm or FakeLocalLLMClient()

    # 受診ファクトリの override
    def _override_make_create_encounter():  # type: ignore[no-untyped-def]
        patient_repo = PatientRepository(session)
        encounter_repo = EncounterRepository(session)
        audit_repo = AuditLogRepository(session)

        async def _create(
            patient_id,  # type: ignore[no-untyped-def]
            encountered_at,
            clinician_id,
        ):
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

    # 患者ファクトリの override (患者作成用ヘルパー呼び出しのため)
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
            return await find_patient_by_id(
                patient_id=patient_id,
                patient_repo=patient_repo,
            )

        return _find

    def _override_make_find_patient_by_mrn():  # type: ignore[no-untyped-def]
        patient_repo = PatientRepository(session)

        async def _find(mrn):  # type: ignore[no-untyped-def]
            return await find_patient_by_mrn(mrn=mrn, patient_repo=patient_repo)

        return _find

    def _override_make_generate_record_draft():  # type: ignore[no-untyped-def]
        encounter_repo = EncounterRepository(session)
        draft_repo = RecordDraftRepository(session)
        audit_repo = AuditLogRepository(session)

        async def _generate(clinical_input, encounter_id):  # type: ignore[no-untyped-def]
            draft = await generate_record_draft(
                clinical_input=clinical_input,
                encounter_id=encounter_id,
                llm=_llm,
                encounter_repo=encounter_repo,
                draft_repo=draft_repo,
                audit_repo=audit_repo,
            )
            await session.flush()
            return draft

        return _generate

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

    def _override_make_find_chain_for_final():  # type: ignore[no-untyped-def]
        final_repo = RecordFinalRepository(session)

        async def _find_chain(final_id):  # type: ignore[no-untyped-def]
            return await find_chain_for_final(final_id=final_id, final_repo=final_repo)

        return _find_chain

    def _override_make_list_finals_by_encounter():  # type: ignore[no-untyped-def]
        final_repo = RecordFinalRepository(session)

        async def _list(encounter_id):  # type: ignore[no-untyped-def]
            return await list_finals_by_encounter(
                encounter_id=encounter_id,
                final_repo=final_repo,
            )

        return _list

    test_app = FastAPI()
    test_app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    test_app.add_exception_handler(
        RequestValidationError,
        request_validation_exception_handler,  # type: ignore[arg-type]
    )
    test_app.add_exception_handler(Exception, unhandled_exception_handler)
    test_app.include_router(patients_router, prefix="")
    test_app.include_router(encounters_router, prefix="")
    test_app.include_router(drafts_router, prefix="")
    test_app.include_router(finals_router, prefix="")
    test_app.dependency_overrides[make_create_encounter] = _override_make_create_encounter
    test_app.dependency_overrides[make_find_encounter_by_id] = _override_make_find_encounter_by_id
    test_app.dependency_overrides[make_list_encounters_by_patient] = (
        _override_make_list_encounters_by_patient
    )
    test_app.dependency_overrides[make_create_patient] = _override_make_create_patient
    test_app.dependency_overrides[make_find_patient_by_id] = _override_make_find_patient_by_id
    test_app.dependency_overrides[make_find_patient_by_mrn] = _override_make_find_patient_by_mrn
    test_app.dependency_overrides[make_generate_record_draft] = _override_make_generate_record_draft
    test_app.dependency_overrides[make_find_draft_by_id] = _override_make_find_draft_by_id
    test_app.dependency_overrides[make_edit_record_draft] = _override_make_edit_record_draft
    test_app.dependency_overrides[make_finalize_draft_to_record_final] = (
        _override_make_finalize_draft_to_record_final
    )
    test_app.dependency_overrides[make_find_final_by_id] = _override_make_find_final_by_id
    test_app.dependency_overrides[make_correct_record_final] = _override_make_correct_record_final
    test_app.dependency_overrides[make_find_chain_for_final] = _override_make_find_chain_for_final
    test_app.dependency_overrides[make_list_finals_by_encounter] = (
        _override_make_list_finals_by_encounter
    )
    test_app.dependency_overrides[get_llm_client] = lambda: _llm
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
def client(session: AsyncSession) -> TestClient:
    """テスト用クライアント。"""
    app = _make_test_app(session)
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# ヘルパー: 患者と受診を作成する
# ---------------------------------------------------------------------------


def _create_patient(client: TestClient, mrn: str = "MRN-ENC-001") -> httpx.Response:
    return client.post(
        "/patients",
        json={
            "mrn": mrn,
            "family_name": "山田",
            "given_name": "太郎",
            "date_of_birth": "1985-04-10",
        },
    )


def _create_encounter(
    client: TestClient,
    patient_id: str,
    encountered_at: str = "2024-01-15T09:00:00Z",
) -> httpx.Response:
    return client.post(
        "/encounters",
        json={
            "patient_id": patient_id,
            "encountered_at": encountered_at,
            "clinician_id": str(uuid4()),
        },
    )


# ---------------------------------------------------------------------------
# (a) POST /encounters 201 — 正常作成
# ---------------------------------------------------------------------------


class TestPostEncounter:
    def test_201_on_create(self, client: TestClient) -> None:
        patient_resp = _create_patient(client)
        assert patient_resp.status_code == 201
        patient_id = patient_resp.json()["id"]

        resp = _create_encounter(client, patient_id)

        assert resp.status_code == 201
        body = resp.json()
        assert body["patient_id"] == patient_id
        assert "id" in body
        assert "encountered_at" in body
        assert "clinician_id" in body
        assert "created_at" in body

    def test_response_has_only_encounter_read_fields(self, client: TestClient) -> None:
        """EncounterRead の宣言フィールドのみがレスポンスに含まれる。"""
        patient_id = _create_patient(client).json()["id"]
        resp = _create_encounter(client, patient_id)

        assert resp.status_code == 201
        expected = {"id", "patient_id", "encountered_at", "clinician_id", "created_at"}
        assert set(resp.json().keys()) == expected

    # -------------------------------------------------------------------------
    # (b) POST /encounters 存在しない patient_id → 404
    # -------------------------------------------------------------------------

    def test_404_on_nonexistent_patient(self, client: TestClient) -> None:
        resp = _create_encounter(client, str(uuid4()))

        assert resp.status_code == 404
        body = resp.json()
        assert body["code"] == "patient_not_found"
        assert "message" in body

    def test_404_message_does_not_echo_uuid(self, client: TestClient) -> None:
        """404 エラーメッセージに patient_id が含まれない (PHI ルール)。"""
        missing_id = str(uuid4())
        resp = _create_encounter(client, missing_id)

        assert resp.status_code == 404
        body = resp.json()
        assert missing_id not in body.get("message", "")

    # -------------------------------------------------------------------------
    # (c) POST /encounters 余分フィールド → 422
    # -------------------------------------------------------------------------

    def test_422_on_extra_field(self, client: TestClient) -> None:
        """extra='forbid' により余分フィールドで 422 を返す。"""
        patient_id = _create_patient(client).json()["id"]
        resp = client.post(
            "/encounters",
            json={
                "patient_id": patient_id,
                "encountered_at": "2024-01-15T09:00:00Z",
                "clinician_id": str(uuid4()),
                "unexpected_field": "value",
            },
        )
        assert resp.status_code == 422
        body = resp.json()
        assert body["code"] == "validation_error"

    def test_422_on_missing_required_field(self, client: TestClient) -> None:
        """必須フィールド欠落で 422 を返す。"""
        resp = client.post(
            "/encounters",
            json={
                "patient_id": str(uuid4()),
                # encountered_at が欠落
                "clinician_id": str(uuid4()),
            },
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# (d) GET /encounters/{id} 200 / (e) 404
# ---------------------------------------------------------------------------


class TestGetEncounterById:
    def test_200_on_existing_encounter(self, client: TestClient) -> None:
        patient_id = _create_patient(client).json()["id"]
        encounter_id = _create_encounter(client, patient_id).json()["id"]

        resp = client.get(f"/encounters/{encounter_id}")

        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == encounter_id
        assert body["patient_id"] == patient_id

    def test_404_on_nonexistent_encounter(self, client: TestClient) -> None:
        resp = client.get(f"/encounters/{uuid4()}")

        assert resp.status_code == 404
        body = resp.json()
        assert body["code"] == "encounter_not_found"

    def test_404_message_does_not_echo_uuid(self, client: TestClient) -> None:
        """404 エラーメッセージに encounter_id が含まれない (PHI ルール)。"""
        missing_id = str(uuid4())
        resp = client.get(f"/encounters/{missing_id}")

        assert resp.status_code == 404
        body = resp.json()
        assert missing_id not in body.get("message", "")

    def test_response_fields_complete(self, client: TestClient) -> None:
        """EncounterRead の全フィールドが返される。"""
        patient_id = _create_patient(client).json()["id"]
        encounter_id = _create_encounter(client, patient_id).json()["id"]

        resp = client.get(f"/encounters/{encounter_id}")

        expected = {"id", "patient_id", "encountered_at", "clinician_id", "created_at"}
        assert set(resp.json().keys()) == expected


# ---------------------------------------------------------------------------
# (f) GET /patients/{id}/encounters 200 — 空リスト
# (g) GET /patients/{id}/encounters 200 — 複数、encountered_at 降順
# (h) GET /patients/{id}/encounters 404 — 存在しない患者
# ---------------------------------------------------------------------------


class TestGetEncountersByPatient:
    def test_200_empty_list_on_no_encounters(self, client: TestClient) -> None:
        """受診がない患者は空リストを返す (404 ではない)。"""
        patient_id = _create_patient(client, mrn="MRN-EMPTY").json()["id"]

        resp = client.get(f"/patients/{patient_id}/encounters")

        assert resp.status_code == 200
        assert resp.json() == []

    def test_200_returns_encounters_ordered_desc(self, client: TestClient) -> None:
        """複数受診が encountered_at 降順で返される。"""
        patient_id = _create_patient(client, mrn="MRN-MULTI").json()["id"]

        dates = [
            "2024-01-10T09:00:00Z",
            "2024-03-20T09:00:00Z",
            "2024-02-05T09:00:00Z",
        ]
        for dt in dates:
            resp = _create_encounter(client, patient_id, encountered_at=dt)
            assert resp.status_code == 201

        resp = client.get(f"/patients/{patient_id}/encounters")
        assert resp.status_code == 200
        bodies = resp.json()
        assert len(bodies) == 3
        # encountered_at 降順確認
        assert bodies[0]["encountered_at"] > bodies[1]["encountered_at"]
        assert bodies[1]["encountered_at"] > bodies[2]["encountered_at"]

    def test_404_on_nonexistent_patient(self, client: TestClient) -> None:
        """存在しない patient_id で 404 を返す。"""
        resp = client.get(f"/patients/{uuid4()}/encounters")

        assert resp.status_code == 404
        body = resp.json()
        assert body["code"] == "patient_not_found"

    def test_404_message_does_not_echo_uuid(self, client: TestClient) -> None:
        """404 エラーメッセージに patient_id が含まれない (PHI ルール)。"""
        missing_id = str(uuid4())
        resp = client.get(f"/patients/{missing_id}/encounters")

        assert resp.status_code == 404
        body = resp.json()
        assert missing_id not in body.get("message", "")


# ---------------------------------------------------------------------------
# (j) GET /encounters/{id}/finals — 空リスト
# (k) GET /encounters/{id}/finals — シード後に確定リスト返す
# (l) GET /encounters/{id}/finals — 未知 encounter_id でも 200 空リスト
# ---------------------------------------------------------------------------


class TestGetFinalsByEncounter:
    def test_200_empty_list_when_no_finals(self, client: TestClient) -> None:
        """確定カルテがない受診は空リストを返す (404 ではない)。"""
        patient_id = _create_patient(client, mrn="MRN-FINALS-ENC-001").json()["id"]
        encounter_id = _create_encounter(client, patient_id).json()["id"]

        resp = client.get(f"/encounters/{encounter_id}/finals")

        assert resp.status_code == 200
        assert resp.json() == []

    def test_200_returns_finals_after_seeding(self, client: TestClient) -> None:
        """確定カルテを作成した後、一覧に含まれる。"""
        patient_id = _create_patient(client, mrn="MRN-FINALS-ENC-002").json()["id"]
        encounter_id = _create_encounter(client, patient_id).json()["id"]

        # 下書き生成 → 確定
        draft_resp = client.post(
            f"/encounters/{encounter_id}/drafts",
            json={"clinical_input": "テスト入力"},
        )
        assert draft_resp.status_code == 201
        draft_id = draft_resp.json()["id"]

        finalize_resp = client.post(
            f"/drafts/{draft_id}/finalize",
            json={"clinician_id": str(uuid4())},
        )
        assert finalize_resp.status_code == 201
        final_id = finalize_resp.json()["id"]

        resp = client.get(f"/encounters/{encounter_id}/finals")

        assert resp.status_code == 200
        bodies = resp.json()
        assert len(bodies) == 1
        assert bodies[0]["id"] == final_id
        assert bodies[0]["encounter_id"] == encounter_id

    def test_200_empty_list_on_unknown_encounter(self, client: TestClient) -> None:
        """未知 encounter_id でも 404 ではなく空リストを返す (ユースケース仕様)。"""
        resp = client.get(f"/encounters/{uuid4()}/finals")

        assert resp.status_code == 200
        assert resp.json() == []
