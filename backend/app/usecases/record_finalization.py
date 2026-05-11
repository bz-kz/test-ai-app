"""確定カルテ作成ユースケース。

下書きを確定カルテに昇格させ、監査ログを記録する。
インフラ層リポジトリのみを経由する — 直接 SQL を書かない。
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domain.entities import AuditAction, AuditLog, RecordFinal
from app.infrastructure.db.repositories import AuditLogRepository, RecordFinalRepository

logger = logging.getLogger(__name__)


async def finalize_record(
    *,
    encounter_id: UUID,
    content: str,
    clinician_id: UUID,
    confidence: float | None,
    predecessor_id: UUID | None,
    final_repo: RecordFinalRepository,
    audit_repo: AuditLogRepository,
) -> RecordFinal:
    """下書き内容を確定カルテとして永続化し、監査ログを残す。

    predecessor_id が指定された場合は訂正版として扱う。
    内容 (content) は PHI を含むためログに渡さない。
    """
    now = datetime.now(tz=UTC)
    record = RecordFinal(
        id=uuid4(),
        encounter_id=encounter_id,
        content=content,
        confidence=confidence,
        clinician_id=clinician_id,
        predecessor_id=predecessor_id,
        created_at=now,
    )
    await final_repo.add(record)

    action = AuditAction.FINAL_CORRECT if predecessor_id else AuditAction.FINAL_CREATE
    audit = AuditLog(
        id=uuid4(),
        at=now,
        actor=clinician_id,
        action=action,
        target_kind="record_final",
        target_id=record.id,
        # PHI を含まないメタデータのみ記録する
        meta_json=json.dumps({"predecessor_id": str(predecessor_id) if predecessor_id else None}),
    )
    await audit_repo.append(audit)

    # content は PHI のためログに出力しない
    logger.info(
        "record finalized: id=%s clinician_id=%s action=%s",
        record.id,
        clinician_id,
        action.value,
    )
    return record
