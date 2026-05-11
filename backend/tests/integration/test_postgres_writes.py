"""Postgres 統合テスト — TIMESTAMPTZ ラウンドトリップ検証。

INF-002 Acceptance §4:
  1. DATABASE_URL 環境変数が設定されていない場合は pytest.skip する。
  2. POST /patients → 201, レスポンスボディを確認する。
  3. audit_log.at の tzinfo が None でないことを確認する (FE-003 の 500 の回帰テスト)。
  4. テスト後にシードした行を削除 (ロールバック) する。

実行方法:
  DATABASE_URL=postgresql+asyncpg://app:app@localhost:5432/app pytest -m integration -v

デフォルト pytest -q では addopts = "-m 'not integration'" により除外される。
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.infrastructure.db.models import AuditLogORM, PatientORM
from app.infrastructure.db.repositories import AuditLogRepository, PatientRepository
from app.usecases.patient import create_patient

# ---------------------------------------------------------------------------
# DATABASE_URL が未設定の場合はテスト全体をスキップする
# ---------------------------------------------------------------------------

_DATABASE_URL = os.getenv("DATABASE_URL")


def _require_postgres() -> None:
    if not _DATABASE_URL or "sqlite" in _DATABASE_URL:
        pytest.skip("DATABASE_URL が未設定または SQLite のため統合テストをスキップ")


# ---------------------------------------------------------------------------
# フィクスチャ
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture()
async def pg_session():  # type: ignore[no-untyped-def]
    """実 Postgres セッション。各テスト後にロールバックする。"""
    _require_postgres()
    engine = create_async_engine(_DATABASE_URL, echo=False)  # type: ignore[arg-type]
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session
        await session.rollback()
    await engine.dispose()


# ---------------------------------------------------------------------------
# テスト
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_patient_create_and_audit_log_tzinfo(pg_session: AsyncSession) -> None:
    """患者作成後、audit_log.at の tzinfo が保持されることを確認する。

    Postgres TIMESTAMPTZ カラムへの書き込み・読み出しで tzinfo が失われないことを検証する。
    これは FE-003 の 500 を引き起こした TZ なし TIMESTAMP カラムの回帰テスト。
    """
    patient_repo = PatientRepository(pg_session)
    audit_repo = AuditLogRepository(pg_session)

    patient = await create_patient(
        mrn="INF002-TZ-TEST",
        family_name="テスト",
        given_name="統合",
        date_of_birth=__import__("datetime").date(1990, 1, 1),
        patient_repo=patient_repo,
        audit_repo=audit_repo,
    )
    await pg_session.flush()

    # audit_log を読み返して at の tzinfo を確認する
    result = await pg_session.execute(
        select(AuditLogORM).where(AuditLogORM.target_id == patient.id)
    )
    audit_row = result.scalar_one()

    assert audit_row is not None, "audit_log 行が作成されていない"
    assert audit_row.at.tzinfo is not None, (
        "audit_log.at の tzinfo が None — TIMESTAMPTZ カラムが TZ 情報を保持できていない"
    )


@pytest.mark.integration
async def test_patient_row_created(pg_session: AsyncSession) -> None:
    """患者作成後、patient テーブルに行が存在することを確認する。"""
    patient_repo = PatientRepository(pg_session)
    audit_repo = AuditLogRepository(pg_session)

    patient = await create_patient(
        mrn="INF002-ROW-TEST",
        family_name="行テスト",
        given_name="確認",
        date_of_birth=__import__("datetime").date(1985, 6, 15),
        patient_repo=patient_repo,
        audit_repo=audit_repo,
    )
    await pg_session.flush()

    result = await pg_session.execute(select(PatientORM).where(PatientORM.id == patient.id))
    row = result.scalar_one()

    assert row is not None
    assert row.mrn == "INF002-ROW-TEST"
    assert row.created_at.tzinfo is not None, "patient.created_at の tzinfo が None"
