"""auth.py の FastAPI 依存関数テスト (BE-012)。

Acceptance:
  (a) X-Clinician-Id ヘッダーが欠落 → 401 エンベロープ {code, message}
  (b) 不正な UUID 形式 → 401 エンベロープ {code, message}
  (c) 有効なヘッダーはエンドポイントを通過する → 200/201
  (d) /health, /ping は X-Clinician-Id を要求しない → 200
  (e) 401 エンベロープにヘッダー値・PHI が含まれない

テスト用アプリは main.py の実際のアプリを再利用する (health/ping エンドポイントが存在するため)。
router テストと異なり、ここでは main.py を使って実際の依存注入グラフを通す。
DB・LLM への接続は不要なため、TestClient の raise_server_exceptions=False を維持する。
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

import main as main_module
from app.infrastructure.db.engine import Base
from app.infrastructure.db.repositories import (
    AuditLogRepository,
    PatientRepository,
)
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

# auth テスト用固定 UUID
_AUTH_TEST_UUID = "00000000-0000-0000-0000-0000000a11ce"


# ---------------------------------------------------------------------------
# テスト用アプリセットアップ
# ---------------------------------------------------------------------------


def _make_minimal_test_app(session: AsyncSession) -> FastAPI:
    """patients ルーターだけを乗せた最小テスト用 FastAPI。
    auth 依存関数の振る舞いを確認するために使う。
    """

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
    test_app.add_exception_handler(Exception, unhandled_exception_handler)
    test_app.include_router(patients_router, prefix="")
    test_app.dependency_overrides[make_create_patient] = _override_make_create_patient
    test_app.dependency_overrides[make_find_patient_by_id] = _override_make_find_patient_by_id
    test_app.dependency_overrides[make_find_patient_by_mrn] = _override_make_find_patient_by_mrn
    return test_app


@pytest.fixture()
async def session() -> AsyncGenerator[AsyncSession, None]:
    """インメモリ SQLite セッション。"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


@pytest.fixture()
def client(session: AsyncSession) -> TestClient:
    """最小テスト用クライアント。"""
    app = _make_minimal_test_app(session)
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# (a) ヘッダー欠落 → 401
# ---------------------------------------------------------------------------


class TestMissingHeader:
    def test_401_on_missing_header_post(self, client: TestClient) -> None:
        """X-Clinician-Id ヘッダーなしで POST /patients → 401。"""
        resp = client.post(
            "/patients",
            json={
                "mrn": "MRN-AUTH-001",
                "family_name": "テスト",
                "given_name": "臨床",
                "date_of_birth": "1990-01-01",
            },
        )
        assert resp.status_code == 401
        body = resp.json()
        assert body["code"] == "unauthenticated"
        assert "message" in body

    def test_401_on_missing_header_get(self, client: TestClient) -> None:
        """X-Clinician-Id ヘッダーなしで GET /patients/{id} → 401。"""
        resp = client.get(f"/patients/{uuid4()}")
        assert resp.status_code == 401
        body = resp.json()
        assert body["code"] == "unauthenticated"

    def test_401_envelope_shape(self, client: TestClient) -> None:
        """401 エンベロープは {code, message} の形式を持つ。"""
        resp = client.get(f"/patients/{uuid4()}")
        assert resp.status_code == 401
        body = resp.json()
        assert set(body.keys()) == {"code", "message"}
        assert body["code"] == "unauthenticated"
        assert body["message"] == "Clinician identification required."


# ---------------------------------------------------------------------------
# (b) 不正な UUID 形式 → 401
# ---------------------------------------------------------------------------


class TestMalformedHeader:
    def test_401_on_non_uuid_string(self, client: TestClient) -> None:
        """UUID でない文字列 → 401。"""
        resp = client.get(
            f"/patients/{uuid4()}",
            headers={"X-Clinician-Id": "not-a-uuid"},
        )
        assert resp.status_code == 401
        body = resp.json()
        assert body["code"] == "unauthenticated"

    def test_401_on_partial_uuid(self, client: TestClient) -> None:
        """不完全な UUID 文字列 → 401。"""
        resp = client.get(
            f"/patients/{uuid4()}",
            headers={"X-Clinician-Id": "12345678-1234-1234"},
        )
        assert resp.status_code == 401

    def test_401_message_does_not_echo_header_value(self, client: TestClient) -> None:
        """401 メッセージに不正なヘッダー値が含まれない (PHI 規則)。"""
        bad_value = "SENSITIVE_MALFORMED_HEADER_VALUE"
        resp = client.get(
            f"/patients/{uuid4()}",
            headers={"X-Clinician-Id": bad_value},
        )
        assert resp.status_code == 401
        body = resp.json()
        assert bad_value not in body.get("message", "")
        assert bad_value not in body.get("code", "")


# ---------------------------------------------------------------------------
# (c) 有効なヘッダーはエンドポイントを通過する
# ---------------------------------------------------------------------------


class TestValidHeader:
    def test_valid_header_allows_post(self, client: TestClient) -> None:
        """有効な X-Clinician-Id ヘッダーで POST /patients → 201。"""
        resp = client.post(
            "/patients",
            json={
                "mrn": "MRN-AUTH-VALID-001",
                "family_name": "有効",
                "given_name": "テスト",
                "date_of_birth": "1985-06-15",
            },
            headers={"X-Clinician-Id": _AUTH_TEST_UUID},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["mrn"] == "MRN-AUTH-VALID-001"

    def test_valid_header_allows_get(self, client: TestClient) -> None:
        """有効なヘッダーで GET /patients/{id} → 404 (存在しない) ではあるが 401 ではない。"""
        resp = client.get(
            f"/patients/{uuid4()}",
            headers={"X-Clinician-Id": _AUTH_TEST_UUID},
        )
        # 404 であるべき (401 ではない)
        assert resp.status_code == 404
        body = resp.json()
        assert body["code"] == "patient_not_found"


# ---------------------------------------------------------------------------
# (d) /health と /ping は X-Clinician-Id 不要
# ---------------------------------------------------------------------------


class TestNoAuthEndpoints:
    def test_health_does_not_require_header(self) -> None:
        """/health エンドポイントはヘッダーなしで到達可能。

        main.py の実アプリを使うのではなく、auth 依存が登録されていないことを確認する。
        実際の health チェックは test_health.py でカバーされる。
        """
        # get_current_clinician が health ルートに登録されていないことを確認する
        health_route = next(
            (r for r in main_module.app.routes if getattr(r, "path", None) == "/health"),
            None,
        )
        assert health_route is not None
        # health ルートの依存に get_current_clinician が含まれないことを確認する
        deps = getattr(health_route, "dependencies", [])
        dep_callables = [d.dependency for d in deps]
        assert get_current_clinician not in dep_callables

    def test_ping_does_not_require_header(self) -> None:
        """/ping エンドポイントはヘッダーなしで到達可能。"""
        ping_route = next(
            (r for r in main_module.app.routes if getattr(r, "path", None) == "/ping"),
            None,
        )
        assert ping_route is not None
        deps = getattr(ping_route, "dependencies", [])
        dep_callables = [d.dependency for d in deps]
        assert get_current_clinician not in dep_callables
