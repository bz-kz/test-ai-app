"""SQLAlchemy 非同期エンジンとセッションファクトリ。

DATABASE_URL 環境変数から接続文字列を読む。
テスト時は sqlalchemy.ext.asyncio の create_async_engine に
sqlite+aiosqlite:// を渡すことでインメモリ DB を使える。
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

# DATABASE_URL が未設定の場合はテスト用インメモリ SQLite にフォールバックする。
# 本番 compose では必ず設定されていることを前提とする。
_DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:///:memory:",
)

engine = create_async_engine(
    _DATABASE_URL,
    # SQLite の場合はチェックを無効化する (asyncio ドライバは元来スレッドセーフ)
    connect_args={"check_same_thread": False} if "sqlite" in _DATABASE_URL else {},
    echo=False,
)

_async_session_factory = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


class Base(DeclarativeBase):
    """全 ORM モデルの共通ベース。"""


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI の Depends() に渡す非同期セッションジェネレータ。"""
    async with _async_session_factory() as session:
        yield session
