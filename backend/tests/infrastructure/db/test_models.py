"""ORM モデルのイミュータビリティと PHI フラグのユニットテスト。

SQLite インメモリ DB を使い、Postgres なしで実行できる。
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.infrastructure.db.engine import Base
from app.infrastructure.db.logging_filter import get_phi_column_names
from app.infrastructure.db.models import (
    PatientORM,
    RecordFinalORM,
)

# ---------------------------------------------------------------------------
# テスト用非同期エンジン/セッションファクトリ
# ---------------------------------------------------------------------------


@pytest.fixture()
async def async_session() -> AsyncGenerator[AsyncSession, None]:
    """インメモリ SQLite で全テーブルを作成しセッションを返す。"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        # SQLite は Enum 型を TEXT として扱うため audit_action Enum は無視される
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


# ---------------------------------------------------------------------------
# PHI カラムフラグのテスト
# ---------------------------------------------------------------------------


def test_phi_column_names_includes_expected_columns() -> None:
    """phi=True でフラグされたカラム名が期待通り収集されていることを確認する。"""
    names = get_phi_column_names()
    # patient テーブルの PHI カラム
    assert "mrn" in names
    assert "family_name" in names
    assert "given_name" in names
    assert "date_of_birth" in names
    # record_draft / record_final の PHI カラム
    assert "content" in names


def test_patient_mrn_column_has_phi_flag() -> None:
    """PatientORM.mrn カラムに phi=True が設定されていることを確認する。"""
    col = PatientORM.__table__.c["mrn"]
    assert col.info.get("phi") is True


def test_patient_non_phi_column_has_no_phi_flag() -> None:
    """PHI でないカラムに phi フラグがないことを確認する。"""
    col = PatientORM.__table__.c["id"]
    assert not col.info.get("phi")


# ---------------------------------------------------------------------------
# record_final イミュータビリティ: before_flush イベントによる保護
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_final_update_raises_at_flush(async_session: AsyncSession) -> None:
    """record_final 行への UPDATE 試行が before_flush イベントで拒否されることを確認する。"""
    from datetime import datetime
    from uuid import uuid4

    row = RecordFinalORM(
        id=uuid4(),
        encounter_id=uuid4(),
        content="initial content",
        confidence=None,
        clinician_id=uuid4(),
        predecessor_id=None,
        created_at=datetime.now(tz=UTC),
    )
    async_session.add(row)
    await async_session.flush()

    # UPDATE を試みる — before_flush イベントが ValueError を送出するはず
    row.content = "modified content"
    with pytest.raises(ValueError, match="record_final rows are immutable"):
        await async_session.flush()


@pytest.mark.asyncio
async def test_record_final_add_new_row_with_predecessor_succeeds(
    async_session: AsyncSession,
) -> None:
    """訂正版を新規行として追加する正規の訂正パターンが成功することを確認する。"""
    from datetime import datetime
    from uuid import uuid4

    now = datetime.now(tz=UTC)
    original_id = uuid4()
    original = RecordFinalORM(
        id=original_id,
        encounter_id=uuid4(),
        content="original content",
        confidence=None,
        clinician_id=uuid4(),
        predecessor_id=None,
        created_at=now,
    )
    async_session.add(original)
    await async_session.flush()

    # 訂正版: predecessor_id に原版の ID を設定する
    correction = RecordFinalORM(
        id=uuid4(),
        encounter_id=original.encounter_id,
        content="corrected content",
        confidence=None,
        clinician_id=original.clinician_id,
        predecessor_id=original_id,
        created_at=now,
    )
    async_session.add(correction)
    await async_session.flush()  # ValueError が発生しないこと

    assert correction.predecessor_id == original_id


# ---------------------------------------------------------------------------
# RecordFinalRepository に update_* メソッドが存在しないことを確認する
# ---------------------------------------------------------------------------


def test_record_final_repository_has_no_update_method() -> None:
    """RecordFinalRepository が update_* で始まるメソッドを持たないことを確認する。"""
    from app.infrastructure.db.repositories import RecordFinalRepository

    update_methods = [name for name in dir(RecordFinalRepository) if name.startswith("update_")]
    assert update_methods == [], (
        f"RecordFinalRepository must not have update_* methods, found: {update_methods}"
    )
