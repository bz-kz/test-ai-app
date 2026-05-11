"""確定カルテユースケース (BE-007)。

下書きから確定カルテへの昇格と、確定カルテの取得を担当する。
インフラ層リポジトリを経由し、直接 SQL は書かない。
interfaces 層はインポートしない (DDD 方向: usecases → infrastructure → domain)。

PHI ルール:
  - draft.content および final.content は PHI (自由記述の臨床叙述)。
  - ログに出力する際は UUID のみを記録する — content は絶対に含めない。
  - 監査ログの meta_json は "{}" 固定 — PHI を一切含めない。
  - エラーメッセージには UUID・PHI を含めない。
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domain.entities import AuditAction, AuditLog, RecordFinal
from app.infrastructure.db.repositories import (
    AuditLogRepository,
    RecordDraftRepository,
    RecordFinalRepository,
)
from app.usecases.errors import DraftNotFound, EncounterAlreadyFinalized, FinalNotFound

logger = logging.getLogger(__name__)

# 認証機能が未実装のため、プレースホルダーとして固定の臨床医 UUID を使用する。
# 将来の auth Block で JWT/セッションから clinician_id を注入する予定。
_PLACEHOLDER_CLINICIAN_ID = UUID("00000000-0000-0000-0000-000000000001")


async def finalize_draft_to_record_final(
    *,
    draft_id: UUID,
    clinician_id: UUID,
    draft_repo: RecordDraftRepository,
    final_repo: RecordFinalRepository,
    audit_repo: AuditLogRepository,
) -> RecordFinal:
    """下書きを確定カルテに昇格させ、永続化して返す。

    処理順序:
      1. 下書きの存在確認 (DraftNotFound を raise する可能性あり)
      2. 受診に対してすでに確定カルテが存在する場合は EncounterAlreadyFinalized を raise
         (訂正版 predecessor_id チェーンは BE-008 のスコープ)
      3. RecordFinal を作成し RecordFinalRepository.add で永続化
      4. AuditLog (FINAL_CREATE) を追記
      5. 確定カルテを返す (同一トランザクション内)

    content は PHI のためログに出力しない。
    """
    # (1) 下書き存在確認
    draft = await draft_repo.find_by_id(draft_id)
    if draft is None:
        logger.debug("finalize_draft aborted: draft not found")
        raise DraftNotFound

    # (2) 二重確定防止: 受診に確定カルテがすでに存在する場合は拒否する
    existing_final = await final_repo.find_by_encounter(draft.encounter_id)
    if existing_final is not None:
        # encounter_id は UUID — エラーメッセージには含めない
        logger.debug("finalize_draft aborted: encounter already finalized")
        raise EncounterAlreadyFinalized

    # (3) 確定カルテ作成
    now = datetime.now(tz=UTC)
    final = RecordFinal(
        id=uuid4(),
        encounter_id=draft.encounter_id,
        content=draft.content,
        confidence=draft.confidence,
        clinician_id=clinician_id,
        # BE-007 では predecessor_id は常に None; 訂正チェーンは BE-008 で実装
        predecessor_id=None,
        created_at=now,
    )
    await final_repo.add(final)

    # (4) 監査ログ追記: meta_json は PHI を含まない空オブジェクト
    audit = AuditLog(
        id=uuid4(),
        at=now,
        actor=clinician_id,
        action=AuditAction.FINAL_CREATE,
        target_kind="record_final",
        target_id=final.id,
        meta_json="{}",
    )
    await audit_repo.append(audit)

    # PHI をログに書かない — id のみ記録する
    logger.info(
        "record_final created: id=%s draft_id=%s clinician_id=%s",
        final.id,
        draft_id,
        clinician_id,
    )
    return final


async def find_final_by_id(
    *,
    final_id: UUID,
    final_repo: RecordFinalRepository,
) -> RecordFinal:
    """ID で確定カルテを取得する。存在しない場合は FinalNotFound を raise する。

    content は PHI のためログに出力しない。
    """
    final = await final_repo.find_by_id(final_id)
    if final is None:
        logger.debug("record_final not found")
        raise FinalNotFound
    return final
