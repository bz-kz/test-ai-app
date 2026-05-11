"""CORS ミドルウェアのユニットテスト。

INF-002 Acceptance §5:
  (a) 許可オリジンからの OPTIONS プリフライト → 200, access-control-allow-origin: http://localhost:3000
  (b) 不許可オリジンからの OPTIONS プリフライト → ACAO ヘッダーが evil origin を含まない
  (c) 許可オリジンからの単純 GET → ACAO ヘッダーが http://localhost:3000 を含む

TestClient (raise_server_exceptions=False) を使い実 DB なしで実行できる。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from main import app

# ---------------------------------------------------------------------------
# フィクスチャ
# ---------------------------------------------------------------------------

ALLOWED_ORIGIN = "http://localhost:3000"
EVIL_ORIGIN = "http://evil.example.com"


@pytest.fixture(scope="module")
def client() -> TestClient:
    """main.py の app をそのまま使うテストクライアント。DB 不要なテストに限定する。"""
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# (a) 許可オリジンからの OPTIONS プリフライト
# ---------------------------------------------------------------------------


class TestCorsPreflightAllowed:
    def test_preflight_returns_allow_origin(self, client: TestClient) -> None:
        """許可オリジンのプリフライトで ACAO ヘッダーが http://localhost:3000 を返す。"""
        resp = client.options(
            "/patients",
            headers={
                "Origin": ALLOWED_ORIGIN,
                "Access-Control-Request-Method": "POST",
            },
        )
        assert resp.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN

    def test_preflight_includes_post_in_allowed_methods(self, client: TestClient) -> None:
        """許可オリジンのプリフライトで access-control-allow-methods に POST が含まれる。"""
        resp = client.options(
            "/patients",
            headers={
                "Origin": ALLOWED_ORIGIN,
                "Access-Control-Request-Method": "POST",
            },
        )
        allow_methods = resp.headers.get("access-control-allow-methods", "")
        assert "POST" in allow_methods


# ---------------------------------------------------------------------------
# (b) 不許可オリジンからの OPTIONS プリフライト
# ---------------------------------------------------------------------------


class TestCorsPreflightDisallowed:
    def test_preflight_disallowed_origin_no_matching_acao(self, client: TestClient) -> None:
        """不許可オリジンのプリフライトでは ACAO ヘッダーに evil origin が含まれない。

        FastAPI/Starlette は不許可オリジンのプリフライトに対して
        access-control-allow-origin ヘッダーを付与しない (または null を返す)。
        evil origin の値が返らないことをアサートし、ヘッダーの有無に依存しない形にする。
        """
        resp = client.options(
            "/patients",
            headers={
                "Origin": EVIL_ORIGIN,
                "Access-Control-Request-Method": "POST",
            },
        )
        acao = resp.headers.get("access-control-allow-origin", "")
        assert acao != EVIL_ORIGIN

    def test_preflight_disallowed_origin_does_not_echo_evil(self, client: TestClient) -> None:
        """ACAO ヘッダーが evil origin を文字列として含まない。"""
        resp = client.options(
            "/patients",
            headers={
                "Origin": EVIL_ORIGIN,
                "Access-Control-Request-Method": "POST",
            },
        )
        acao = resp.headers.get("access-control-allow-origin", "")
        assert EVIL_ORIGIN not in acao


# ---------------------------------------------------------------------------
# (c) 許可オリジンからの単純 GET クロスオリジンリクエスト
# ---------------------------------------------------------------------------


class TestCorsSimpleRequest:
    def test_get_with_allowed_origin_has_acao_header(self, client: TestClient) -> None:
        """許可オリジンからの GET に対して ACAO ヘッダーが http://localhost:3000 を返す。

        /ping は DB 不要のエンドポイントなので TestClient がそのまま使える。
        CORS ミドルウェアが実際のレスポンスにも ACAO ヘッダーを付与することを確認する。
        """
        resp = client.get(
            "/ping",
            headers={"Origin": ALLOWED_ORIGIN},
        )
        assert resp.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN
