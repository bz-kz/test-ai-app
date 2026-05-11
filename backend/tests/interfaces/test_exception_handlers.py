"""exception_handlers のユニットテスト。

BE-003 Acceptance:
  (a) HTTPException → 正規化エンベロープ
  (b) RequestValidationError → 422, code="validation_error"
  (c) 未補足 Exception → 500, code="internal_error", PHI 漏洩なし
  (d) response_model によるフィールドストリッピング確認
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch  # noqa: F401 — used in TestMainEndpointsRegression

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.interfaces.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
    unhandled_exception_handler,
)
from app.interfaces.schemas import ErrorResponse

# ---------------------------------------------------------------------------
# テスト用 FastAPI アプリ
# ---------------------------------------------------------------------------


def _make_test_app() -> FastAPI:
    """各テストケース用の独立した FastAPI インスタンスを生成する。"""
    from fastapi.exceptions import RequestValidationError
    from starlette.exceptions import HTTPException as StarletteHTTPException

    test_app = FastAPI()
    test_app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    test_app.add_exception_handler(
        RequestValidationError,
        request_validation_exception_handler,  # type: ignore[arg-type]
    )
    test_app.add_exception_handler(Exception, unhandled_exception_handler)
    return test_app


# ---------------------------------------------------------------------------
# (a) HTTPException → 正規化エンベロープ
# ---------------------------------------------------------------------------


class TestHttpExceptionHandler:
    def test_404_returns_not_found_code(self) -> None:
        app = _make_test_app()

        @app.get("/notfound")
        async def _raise_404() -> dict[str, str]:
            raise HTTPException(status_code=404, detail="Resource not found")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/notfound")

        assert resp.status_code == 404
        body = resp.json()
        assert body["code"] == "not_found"
        assert "message" in body
        # ErrorResponse のみ: 余分なフィールドなし
        assert set(body.keys()) == {"code", "message"}

    def test_400_returns_bad_request_code(self) -> None:
        app = _make_test_app()

        @app.get("/badreq")
        async def _raise_400() -> dict[str, str]:
            raise HTTPException(status_code=400, detail="Bad input")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/badreq")

        assert resp.status_code == 400
        assert resp.json()["code"] == "bad_request"

    def test_403_returns_forbidden_code(self) -> None:
        app = _make_test_app()

        @app.get("/forbidden")
        async def _raise_403() -> dict[str, str]:
            raise HTTPException(status_code=403, detail="Forbidden")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/forbidden")

        assert resp.status_code == 403
        assert resp.json()["code"] == "forbidden"

    def test_unknown_4xx_returns_client_error_code(self) -> None:
        app = _make_test_app()

        @app.get("/teapot")
        async def _raise_418() -> dict[str, str]:
            raise HTTPException(status_code=418, detail="I'm a teapot")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/teapot")

        assert resp.status_code == 418
        assert resp.json()["code"] == "client_error"

    def test_detail_object_does_not_leak_as_message(self) -> None:
        """dict 型の detail はそのまま message に変換されない (PHI 保護)。"""
        app = _make_test_app()

        @app.get("/leaktest")
        async def _raise_with_dict_detail() -> dict[str, str]:
            raise HTTPException(
                status_code=404,
                detail={"mrn": "12345678", "msg": "not found"},
            )

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/leaktest")

        assert resp.status_code == 404
        body = resp.json()
        # dict detail は文字列化されず、PHI が message に入らない
        assert "12345678" not in body.get("message", "")


# ---------------------------------------------------------------------------
# (b) RequestValidationError → 422, code="validation_error"
# ---------------------------------------------------------------------------


class TestRequestValidationHandler:
    def test_422_on_missing_required_field(self) -> None:
        app = _make_test_app()

        class CreateItem(BaseModel):
            name: str
            quantity: int

        @app.post("/items", response_model=CreateItem)
        async def _create_item(item: CreateItem) -> CreateItem:
            return item

        client = TestClient(app, raise_server_exceptions=False)
        # quantity フィールドを欠落させる
        resp = client.post("/items", json={"name": "aspirin"})

        assert resp.status_code == 422
        body = resp.json()
        assert body["code"] == "validation_error"
        assert "message" in body
        assert set(body.keys()) == {"code", "message"}

    def test_validation_message_does_not_contain_phi_values(self) -> None:
        """バリデーションエラーのメッセージにリクエスト本文の値が含まれない。"""
        app = _make_test_app()

        class PatientInput(BaseModel):
            mrn: int  # 文字列を渡すと型エラーになる

        @app.post("/patients-test", response_model=PatientInput)
        async def _create_patient(p: PatientInput) -> PatientInput:
            return p

        client = TestClient(app, raise_server_exceptions=False)
        # PHI っぽい値を送信
        resp = client.post(
            "/patients-test",
            json={"mrn": "PATIENT-MRN-SECRET"},
        )

        assert resp.status_code == 422
        body = resp.json()
        # リクエスト値がメッセージに含まれないこと
        assert "PATIENT-MRN-SECRET" not in body.get("message", "")


# ---------------------------------------------------------------------------
# (c) 未補足 Exception → 500, code="internal_error", PHI 漏洩なし
# ---------------------------------------------------------------------------


class TestUnhandledExceptionHandler:
    def test_500_on_unhandled_exception(self) -> None:
        app = _make_test_app()

        @app.get("/crash")
        async def _crash() -> dict[str, str]:
            raise RuntimeError("unexpected internal error")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/crash")

        assert resp.status_code == 500
        body = resp.json()
        assert body["code"] == "internal_error"
        assert "message" in body
        assert set(body.keys()) == {"code", "message"}

    def test_500_message_does_not_contain_internal_details(self) -> None:
        """500 レスポンスに例外の詳細(スタックトレース等)が含まれない。"""
        app = _make_test_app()

        @app.get("/crash-secret")
        async def _crash_with_secret() -> dict[str, str]:
            raise ValueError("patient_mrn=99999999 not found in DB")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/crash-secret")

        assert resp.status_code == 500
        body = resp.json()
        # 内部エラーメッセージや PHI がレスポンスに含まれない
        assert "99999999" not in str(body)
        assert "patient_mrn" not in str(body)
        assert "not found in DB" not in str(body)

    def test_500_response_has_no_phi_from_request_body(self) -> None:
        """リクエストボディの PHI が 500 レスポンスに漏洩しない。"""
        # Body パラメータを Body() で明示してリクエストボディとして受け取る
        from fastapi import Body

        app = _make_test_app()

        @app.post("/process")
        async def _process(
            mrn: str = Body(..., embed=True),
        ) -> dict[str, str]:
            raise RuntimeError("DB connection lost")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/process", json={"mrn": "PHI-SECRET-MRN"})

        assert resp.status_code == 500
        # PHI がレスポンスに含まれない
        assert "PHI-SECRET-MRN" not in resp.text


# ---------------------------------------------------------------------------
# (d) response_model によるフィールドストリッピング
# ---------------------------------------------------------------------------


class TestResponseModelStripping:
    def test_extra_fields_stripped_from_response(self) -> None:
        """response_model に宣言されていないフィールドはレスポンスから除外される。"""
        app = _make_test_app()

        class PublicResponse(BaseModel):
            id: int
            name: str

        @app.get("/items/{item_id}", response_model=PublicResponse)
        async def _get_item(item_id: int) -> dict[str, object]:
            # internal_secret と phi_value は PublicResponse に含まれないため除外される
            return {
                "id": item_id,
                "name": "test-item",
                "internal_secret": "should-be-stripped",
                "phi_value": "patient-name-here",
            }

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/items/42")

        assert resp.status_code == 200
        body = resp.json()
        # response_model で宣言したフィールドのみ
        assert set(body.keys()) == {"id", "name"}
        assert "internal_secret" not in body
        assert "phi_value" not in body

    def test_error_response_model_fields(self) -> None:
        """ErrorResponse は code と message のみを持つ。"""
        err = ErrorResponse(code="not_found", message="Resource not found")
        dumped = err.model_dump()
        assert set(dumped.keys()) == {"code", "message"}


# ---------------------------------------------------------------------------
# main.py の /ping, /health エンドポイントの後退テスト
# ---------------------------------------------------------------------------


class TestMainEndpointsRegression:
    def test_ping_returns_ok(self) -> None:
        from main import app as main_app

        client = TestClient(main_app, raise_server_exceptions=False)
        resp = client.get("/ping")

        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_health_all_ok(self) -> None:
        """Postgres と LLM が到達可能なとき 200 を返す (モック使用)。"""
        from main import app as main_app

        # asyncpg.connect は asyncpg のモジュールに直接パッチする
        conn_mock = AsyncMock()
        conn_mock.close = AsyncMock()
        connect_mock = AsyncMock(return_value=conn_mock)

        with (
            patch("asyncpg.connect", connect_mock),
            patch(
                "app.infrastructure.llm.ollama_client.OllamaLocalLLMClient.ping",
                new_callable=AsyncMock,
                return_value=True,
            ),
        ):
            client = TestClient(main_app, raise_server_exceptions=False)
            resp = client.get("/health")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
