"""Alembic 環境設定。

DATABASE_URL 環境変数から接続文字列を読み、ORM モデルのメタデータを
target_metadata に渡してオートジェネレートを有効にする。

非同期 URL (postgresql+asyncpg://) を直接扱えるように
async_engine_from_config + run_sync パターンを採用している。
同期 psycopg2 パスよりも依存が少なく、アプリ本体と同じドライバを使えるためこちらを選択。
"""

from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection, pool
from sqlalchemy.ext.asyncio import async_engine_from_config

# Alembic Config オブジェクト
config = context.config

# ログ設定
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ORM モデルのメタデータを登録してオートジェネレートを有効にする
# models.py をインポートすることで全テーブル定義が Base.metadata に登録される
import app.infrastructure.db.models  # noqa: E402, F401
from app.infrastructure.db.engine import Base  # noqa: E402

target_metadata = Base.metadata

# DATABASE_URL を環境変数から取得し alembic.ini の設定を上書きする
_db_url = os.getenv("DATABASE_URL")
if _db_url:
    config.set_main_option("sqlalchemy.url", _db_url)


def run_migrations_offline() -> None:
    """オフラインモード: エンジンなしで SQL を標準出力へ出力する。"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """同期コンテキストでマイグレーションを実行する内部ヘルパー。

    非同期エンジンの run_sync() から呼ばれる。
    """
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """オンラインモード: 非同期エンジンを生成して実 DB へマイグレーションを適用する。

    async_engine_from_config を使うことで postgresql+asyncpg:// URL を
    MissingGreenlet エラーなしに扱える。
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
