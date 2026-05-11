"""FastAPI application entry point."""

import logging
import os

import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Medical Record Generator API",
    docs_url=None,  # OpenAPIドキュメントは本番では非公開
    redoc_url=None,
)


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


@app.get("/health", response_model=HealthResponse)
async def health() -> Response:
    """Postgres と llm が両方到達可能なときのみ 200 を返す。"""
    database_url = os.getenv("DATABASE_URL", "")
    llm_base_url = os.getenv("LLM_BASE_URL", "http://llm:11434")

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

    # LLM 疎通確認: Ollama の tags エンドポイントに HEAD リクエスト
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{llm_base_url}/api/tags")
            llm_ok = resp.status_code == 200
    except Exception:
        logger.warning("LLM health check failed")

    all_ok = postgres_ok and llm_ok
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content=HealthResponse(
            status="ok" if all_ok else "degraded",
            postgres=postgres_ok,
            llm=llm_ok,
        ).model_dump(),
    )
