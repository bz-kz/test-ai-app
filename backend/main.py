"""FastAPI アプリケーションエントリポイント。"""

import logging
import os

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.infrastructure.llm import InferenceError, OllamaLocalLLMClient
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
from app.interfaces.schemas import ErrorResponse

logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Medical Record Generator API",
    # 対話 UI (/docs, /redoc) は常時非公開 (CLAUDE.md §2 / backend/SPEC.md#api-surface)
    docs_url=None,
    redoc_url=None,
)

# ---------------------------------------------------------------------------
# グローバル例外ハンドラ登録
# ---------------------------------------------------------------------------

app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
app.add_exception_handler(
    RequestValidationError,
    request_validation_exception_handler,  # type: ignore[arg-type]
)
# InferenceError は Exception のサブクラスなので unhandled_exception_handler より先に登録する
app.add_exception_handler(InferenceError, inference_error_handler)  # type: ignore[arg-type]
app.add_exception_handler(Exception, unhandled_exception_handler)

# ---------------------------------------------------------------------------
# 機能ルーター登録
# ---------------------------------------------------------------------------

app.include_router(patients_router, prefix="")
app.include_router(encounters_router, prefix="")
app.include_router(drafts_router, prefix="")
app.include_router(finals_router, prefix="")

# ---------------------------------------------------------------------------
# 既存エンドポイント: /ping, /health
# ---------------------------------------------------------------------------


class PingResponse(BaseModel):
    status: str


class HealthResponse(BaseModel):
    status: str
    postgres: bool
    llm: bool


@app.get("/ping", response_model=PingResponse)
async def ping() -> PingResponse:
    """コンテナの生存確認専用エンドポイント。依存サービス不問。"""
    return PingResponse(status="ok")


@app.get(
    "/health",
    response_model=HealthResponse,
    responses={503: {"model": ErrorResponse, "description": "サービス劣化状態"}},
)
async def health() -> Response:
    """Postgres と llm が両方到達可能なときのみ 200 を返す。"""
    database_url = os.getenv("DATABASE_URL", "")

    postgres_ok = False
    llm_ok = False

    # Postgres 疎通確認: asyncpg で軽量接続テスト
    try:
        import asyncpg

        # asyncpg DSN は postgresql:// 形式を使う
        dsn = database_url.replace("postgresql+asyncpg://", "postgresql://")
        conn = await asyncpg.connect(dsn, timeout=5)
        await conn.close()
        postgres_ok = True
    except Exception:
        logger.warning("Postgres health check failed")

    # LLM 疎通確認: インフラ層の ping() を経由して直接 httpx は使わない
    llm_client = OllamaLocalLLMClient()
    llm_ok = await llm_client.ping()

    all_ok = postgres_ok and llm_ok
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content=HealthResponse(
            status="ok" if all_ok else "degraded",
            postgres=postgres_ok,
            llm=llm_ok,
        ).model_dump(),
    )
