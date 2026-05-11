"""患者エンドポイントのルーターテスト。

TestClient + インメモリ SQLite を使い、Postgres なしで実行できる。
BE-004 Acceptance:
  (a) POST /patients 201 — 正常作成
  (b) POST /patients 重複 MRN → 409, code="patient_mrn_conflict"
  (c) GET  /patients/{id} 200 — 存在する患者
  (d) GET  /patients/{id} 404 — 存在しない患者 (PHI を echo しない)
  (e) GET  /patients?mrn= 200 — 存在する患者
  (f) GET  /patients?mrn= 404 — 存在しない患者 (PHI を echo しない)
  (g) POST /patients 422 — バリデーションエラー

DI 方針:
  ルーターはユースケースファクトリ依存 (make_create_patient 等) を使うため、
  テストでは各ファクトリを override する。infrastructure を直接参照しない。
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import date
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
from app.infrastructure.db.repositories import AuditLogRepository, PatientRepository
from app.interfaces.auth import get_current_clinician
from app.interfaces.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
    unhandled_exception_handler,
)
from app.interfaces.routers.patients import router as patients_router
from app.usecases.di import (
    make_create_patient,
    make_find_patient_by_id,
    make_find_patient_by_mrn,
)
from app.usecases.patient import create_patient, find_patient_by_id, find_patient_by_mrn
from tests.conftest import TEST_CLINICIAN_ID

# ---------------------------------------------------------------------------
# テスト用アプリとインメモリ DB のセットアップ
# ---------------------------------------------------------------------------


def _make_test_app(session: AsyncSession) -> FastAPI:
    """インメモリ DB セッションをユースケースファクトリ DI に差し込んだ
    テスト用 FastAPI を生成する。"""

    # 各ファクトリを同一セッションを使うクロージャで上書きする
    def _override_make_create_patient():  # type: ignore[no-untyped-def]
        patient_repo = PatientRepository(session)
        audit_repo = AuditLogRepository(session)

        async def _create(
            mrn: str,
            family_name: str,
            given_name: str,
            date_of_birth: date,
            clinician_id,  # type: ignore[no-untyped-def]
        ):
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
            return await find_patient_by_id(
                patient_id=patient_id,
                patient_repo=patient_repo,
            )

        return _find

    def _override_make_find_patient_by_mrn():  # type: ignore[no-untyped-def]
        patient_repo = PatientRepository(session)

        async def _find(mrn):  # type: ignore[no-untyped-def]
            return await find_patient_by_mrn(
                mrn=mrn,
                patient_repo=patient_repo,
            )

        return _find

    test_app = FastAPI()
    test_app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    test_app.add_exception_handler(
        RequestValidationError,
        request_validation_exception_handler,  # type: ignore[arg-type]
    )
    test_app.add_exception_handler(Exception, unhandled_exception_handler)
    test_app.include_router(patients_router, prefix="")
    test_app.dependency_overrides[make_create_patient] = _override_make_create_patient
    test_app.dependency_overrides[make_find_patient_by_id] = _override_make_find_patient_by_id
    test_app.dependency_overrides[make_find_patient_by_mrn] = _override_make_find_patient_by_mrn
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
def client(session: AsyncSession) -> TestClient:
    """テスト用クライアント。"""
    app = _make_test_app(session)
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# ヘルパー: 患者を POST /patients で作成する
# ---------------------------------------------------------------------------


def _create_patient(client: TestClient, mrn: str = "MRN-TEST-001") -> httpx.Response:
    return client.post(
        "/patients",
        json={
            "mrn": mrn,
            "family_name": "山田",
            "given_name": "太郎",
            "date_of_birth": "1985-04-10",
        },
    )


# ---------------------------------------------------------------------------
# (a) POST /patients 201 — 正常作成
# ---------------------------------------------------------------------------


class TestPostPatient:
    def test_201_on_create(self, client: TestClient) -> None:
        resp = _create_patient(client)

        assert resp.status_code == 201
        body = resp.json()
        assert body["mrn"] == "MRN-TEST-001"
        assert body["family_name"] == "山田"
        assert body["given_name"] == "太郎"
        assert body["date_of_birth"] == "1985-04-10"
        assert "id" in body
        assert "created_at" in body

    def test_response_has_only_patient_read_fields(self, client: TestClient) -> None:
        """PatientRead の宣言フィールドのみがレスポンスに含まれる。"""
        resp = _create_patient(client)

        assert resp.status_code == 201
        body = resp.json()
        expected = {"id", "mrn", "family_name", "given_name", "date_of_birth", "created_at"}
        assert set(body.keys()) == expected

    # ---------------------------------------------------------------------------
    # (b) POST /patients 重複 MRN → 409
    # ---------------------------------------------------------------------------

    def test_409_on_duplicate_mrn(self, client: TestClient) -> None:
        _create_patient(client, mrn="MRN-DUPE")
        resp = _create_patient(client, mrn="MRN-DUPE")

        assert resp.status_code == 409
        body = resp.json()
        assert body["code"] == "patient_mrn_conflict"
        assert "message" in body

    def test_409_message_does_not_echo_mrn(self, client: TestClient) -> None:
        """409 エラーメッセージに MRN 値が含まれない (PHI ルール)。"""
        mrn_value = "SENSITIVE-MRN-9999"
        _create_patient(client, mrn=mrn_value)
        resp = _create_patient(client, mrn=mrn_value)

        assert resp.status_code == 409
        body = resp.json()
        assert mrn_value not in body.get("message", "")

    # ---------------------------------------------------------------------------
    # (g) POST /patients 422 — バリデーションエラー
    # ---------------------------------------------------------------------------

    def test_422_on_missing_required_field(self, client: TestClient) -> None:
        """必須フィールド欠落時に 422 を返す。"""
        resp = client.post(
            "/patients",
            json={
                "mrn": "MRN-MISSING-FIELDS",
                # family_name, given_name, date_of_birth が欠落
            },
        )
        assert resp.status_code == 422
        body = resp.json()
        assert body["code"] == "validation_error"

    def test_422_on_invalid_date(self, client: TestClient) -> None:
        """不正な日付形式で 422 を返す。"""
        resp = client.post(
            "/patients",
            json={
                "mrn": "MRN-BAD-DATE",
                "family_name": "Test",
                "given_name": "User",
                "date_of_birth": "not-a-date",
            },
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# (c) GET /patients/{id} 200 / (d) 404
# ---------------------------------------------------------------------------


class TestGetPatientById:
    def test_200_on_existing_patient(self, client: TestClient) -> None:
        create_resp = _create_patient(client)
        patient_id = create_resp.json()["id"]

        resp = client.get(f"/patients/{patient_id}")

        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == patient_id
        assert body["mrn"] == "MRN-TEST-001"

    def test_404_on_nonexistent_id(self, client: TestClient) -> None:
        resp = client.get(f"/patients/{uuid4()}")

        assert resp.status_code == 404
        body = resp.json()
        assert body["code"] == "patient_not_found"

    def test_404_message_does_not_echo_id(self, client: TestClient) -> None:
        """404 エラーメッセージに patient_id が含まれない (PHI ルール)。"""
        search_id = str(uuid4())
        resp = client.get(f"/patients/{search_id}")

        assert resp.status_code == 404
        body = resp.json()
        # UUID は PHI ではないが、エラーメッセージの汎用性のため ID を echo しない
        assert search_id not in body.get("message", "")

    def test_response_fields_complete(self, client: TestClient) -> None:
        """PatientRead の全フィールドが返される。"""
        create_resp = _create_patient(client)
        patient_id = create_resp.json()["id"]

        resp = client.get(f"/patients/{patient_id}")

        body = resp.json()
        expected = {"id", "mrn", "family_name", "given_name", "date_of_birth", "created_at"}
        assert set(body.keys()) == expected


# ---------------------------------------------------------------------------
# (e) GET /patients?mrn= 200 / (f) 404
# ---------------------------------------------------------------------------


class TestGetPatientByMrn:
    def test_200_on_existing_mrn(self, client: TestClient) -> None:
        _create_patient(client, mrn="MRN-SEARCH-001")

        resp = client.get("/patients?mrn=MRN-SEARCH-001")

        assert resp.status_code == 200
        body = resp.json()
        assert body["mrn"] == "MRN-SEARCH-001"

    def test_404_on_nonexistent_mrn(self, client: TestClient) -> None:
        resp = client.get("/patients?mrn=MRN-DOES-NOT-EXIST")

        assert resp.status_code == 404
        body = resp.json()
        assert body["code"] == "patient_not_found"

    def test_404_message_does_not_echo_mrn(self, client: TestClient) -> None:
        """404 エラーメッセージに MRN 値が含まれない (PHI ルール)。"""
        sensitive_mrn = "SENSITIVE-MRN-PHI-12345"
        resp = client.get(f"/patients?mrn={sensitive_mrn}")

        assert resp.status_code == 404
        body = resp.json()
        assert sensitive_mrn not in body.get("message", "")

    def test_422_on_empty_mrn(self, client: TestClient) -> None:
        """mrn が空文字列の場合に 422 を返す (min_length=1)。"""
        resp = client.get("/patients?mrn=")

        assert resp.status_code == 422

    def test_422_on_missing_mrn_param(self, client: TestClient) -> None:
        """mrn クエリパラメータが欠落した場合に 422 を返す。"""
        resp = client.get("/patients")

        assert resp.status_code == 422
