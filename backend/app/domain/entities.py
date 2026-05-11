"""ドメインエンティティ: 純粋な dataclass。インフラ・ユースケース層への依存を持たない。

SPEC.md#domain-glossary のカノニカル識別子に準拠する。
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


class AuditAction(str, enum.Enum):
    """audit_log.action に格納する操作種別。"""

    PATIENT_CREATE = "patient_create"
    ENCOUNTER_CREATE = "encounter_create"
    DRAFT_CREATE = "record_draft_create"
    DRAFT_UPDATE = "record_draft_update"
    FINAL_CREATE = "record_final_create"
    FINAL_CORRECT = "record_final_correct"


@dataclass(frozen=True)
class Patient:
    """患者エンティティ。mrn は PHI。"""

    id: UUID
    mrn: str  # PHI: 診察番号
    family_name: str  # PHI
    given_name: str  # PHI
    date_of_birth: datetime  # PHI
    created_at: datetime


@dataclass(frozen=True)
class Encounter:
    """受診エンティティ。patient_id で患者と紐づく。"""

    id: UUID
    patient_id: UUID
    encountered_at: datetime
    clinician_id: UUID
    created_at: datetime


@dataclass(frozen=True)
class RecordDraft:
    """AI 生成のカルテ下書き。臨床医が署名するまでは変更可能。"""

    id: UUID
    encounter_id: UUID
    content: str  # PHI: 臨床記録の本文
    confidence: float | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class RecordFinal:
    """臨床医が署名した確定カルテ。イミュータブル; 訂正は新規行で表現する。

    predecessor_id が None でない行は、predecessor_id が指す行の訂正版を示す。
    """

    id: UUID
    encounter_id: UUID
    content: str  # PHI: 臨床記録の本文
    confidence: float | None
    clinician_id: UUID
    # 訂正時に直前の record_final.id を参照する; None なら初版
    predecessor_id: UUID | None
    created_at: datetime


@dataclass(frozen=True)
class AuditLog:
    """操作監査ログ。append-only; UPDATE は許可しない。"""

    id: UUID
    at: datetime
    actor: UUID  # clinician_id
    action: AuditAction
    target_kind: str
    target_id: UUID
    # 追加メタデータは JSON 文字列として格納する
    meta_json: str = field(default="{}")
