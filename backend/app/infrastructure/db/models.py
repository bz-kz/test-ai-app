"""SQLAlchemy 2.x 宣言的スタイルの ORM モデル。

PHI カラムは `mapped_column(..., info={"phi": True})` でフラグを立てる。
PhiLoggingFilter はこのメタデータを走査してログをマスクする。

record_final はイミュータブル:
  (a) SQLAlchemy の before_flush イベントで UPDATE を拒否する (このファイルで登録)
  (b) RecordFinalRepository に update_* メソッドを定義しない
"""

from __future__ import annotations

import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Enum,
    ForeignKey,
    Text,
    event,
)
from sqlalchemy.orm import Mapped, Session, mapped_column

from .engine import Base


class AuditActionORM(str, enum.Enum):
    """audit_log.action DB Enum。ドメイン層の AuditAction と 1:1 対応。"""

    PATIENT_CREATE = "patient_create"
    ENCOUNTER_CREATE = "encounter_create"
    DRAFT_CREATE = "record_draft_create"
    DRAFT_UPDATE = "record_draft_update"
    FINAL_CREATE = "record_final_create"
    FINAL_CORRECT = "record_final_correct"


class PatientORM(Base):
    """患者テーブル。mrn / family_name / given_name / date_of_birth が PHI。"""

    __tablename__ = "patient"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    mrn: Mapped[str] = mapped_column(info={"phi": True})
    family_name: Mapped[str] = mapped_column(info={"phi": True})
    given_name: Mapped[str] = mapped_column(info={"phi": True})
    date_of_birth: Mapped[datetime] = mapped_column(info={"phi": True})
    created_at: Mapped[datetime] = mapped_column()


class EncounterORM(Base):
    """受診テーブル。患者 ID と医師 ID を保持する。"""

    __tablename__ = "encounter"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey("patient.id"), index=True)
    encountered_at: Mapped[datetime] = mapped_column()
    clinician_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column()


class RecordDraftORM(Base):
    """カルテ下書きテーブル。content が PHI。"""

    __tablename__ = "record_draft"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    encounter_id: Mapped[UUID] = mapped_column(ForeignKey("encounter.id"), index=True)
    content: Mapped[str] = mapped_column(Text, info={"phi": True})
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column()
    updated_at: Mapped[datetime] = mapped_column()


class RecordFinalORM(Base):
    """確定カルテテーブル。イミュータブル — UPDATE は before_flush イベントで拒否。

    訂正版は新規行として追加し、predecessor_id で前版を参照する。
    PHI カラム: content。
    """

    __tablename__ = "record_final"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    encounter_id: Mapped[UUID] = mapped_column(ForeignKey("encounter.id"), index=True)
    content: Mapped[str] = mapped_column(Text, info={"phi": True})
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    clinician_id: Mapped[UUID] = mapped_column()
    # 前版の record_final.id; None なら初版
    predecessor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("record_final.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column()


class AuditLogORM(Base):
    """監査ログテーブル。append-only — UPDATE は before_flush イベントで拒否。"""

    __tablename__ = "audit_log"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(index=True)
    actor: Mapped[UUID] = mapped_column()
    action: Mapped[AuditActionORM] = mapped_column(Enum(AuditActionORM, name="audit_action"))
    target_kind: Mapped[str] = mapped_column()
    target_id: Mapped[UUID] = mapped_column()
    meta_json: Mapped[str] = mapped_column(Text, default="{}")


# ---------------------------------------------------------------------------
# record_final イミュータビリティ強制: (a) SQLAlchemy イベントによる保護
# ---------------------------------------------------------------------------


@event.listens_for(Session, "before_flush")
def _reject_record_final_updates(
    session: Session, flush_context: object, instances: object
) -> None:
    """record_final の UPDATE を flush 前に検出して拒否する。

    既存行への変更は不変条件違反であり、訂正は新規行で表現すること。
    """
    for dirty_obj in session.dirty:
        if isinstance(dirty_obj, RecordFinalORM):
            raise ValueError(
                "record_final rows are immutable. "
                "Create a new row with predecessor_id set to the corrected row's id."
            )
    # audit_log も append-only として保護する
    for dirty_obj in session.dirty:
        if isinstance(dirty_obj, AuditLogORM):
            raise ValueError("audit_log rows are immutable. Corrections must append new rows.")
