"""カルテ下書きユースケース。

下書きの生成・取得を担当する。インフラ層リポジトリと LLM クライアントを経由し、
直接 SQL や LLM 呼び出しは行わない。
interfaces 層はインポートしない (DDD 方向: usecases → infrastructure → domain)。

PHI ルール:
  - clinical_input および draft.content は PHI (自由記述の臨床叙述)。
  - ログに出力する際は mask_phi() を必ず使用すること。
  - 監査ログの meta_json は "{}" 固定 — PHI を一切含めない。
  - InferenceError はそのまま伝播させる (ルーター層で 503 に変換する)。
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domain.entities import AuditAction, AuditLog, RecordDraft
from app.infrastructure.db.repositories import (
    AuditLogRepository,
    EncounterRepository,
    RecordDraftRepository,
)
from app.infrastructure.llm.client import LocalLLMClient
from app.infrastructure.llm.types import GenerateParams
from app.usecases.errors import DraftNotFound, EncounterNotFound
from app.usecases.prompts import build_draft_prompt

logger = logging.getLogger(__name__)

# 認証機能が未実装のため、プレースホルダーとして固定の臨床医 UUID を使用する。
_PLACEHOLDER_CLINICIAN_ID = UUID("00000000-0000-0000-0000-000000000001")


async def generate_record_draft(
    *,
    clinical_input: str,
    encounter_id: UUID,
    llm: LocalLLMClient,
    encounter_repo: EncounterRepository,
    draft_repo: RecordDraftRepository,
    audit_repo: AuditLogRepository,
) -> RecordDraft:
    """AI によるカルテ下書きを生成し、永続化する。

    処理順序:
      1. 受診の存在確認 (EncounterNotFound を raise する可能性あり)
      2. プロンプト構築 (build_draft_prompt — 副作用なし)
      3. LLM 呼び出し (InferenceError を raise する可能性あり)
      4. RecordDraft の永続化 + AuditLog の追記 (同一トランザクション)
      5. 生成した下書きを返す

    InferenceError はキャッチせずにそのまま伝播させる。
    ルーター層のグローバルハンドラが 503 に変換する。

    PHI はプロンプト本文に含まれるがローカルモデル専用のため許可されている
    (local-llm-and-phi.md §3)。ログへの PHI 出力は禁止。
    """
    # (1) 受診存在確認: 存在しない場合は EncounterNotFound を raise する
    encounter = await encounter_repo.find_by_id(encounter_id)
    if encounter is None:
        # encounter_id は UUID — エラーメッセージには含めない
        logger.debug("draft generation aborted: encounter not found")
        raise EncounterNotFound

    # (2) プロンプト構築: clinical_input は PHI のため debug ログもマスクする
    prompt = build_draft_prompt(clinical_input)
    logger.debug("draft prompt built: encounter_id=%s length=%d", encounter_id, len(prompt))

    # (3) LLM 呼び出し: InferenceError はキャッチせず伝播させる
    # PHI を含む clinical_input / response.text はログに書かない
    response = await llm.generate(prompt, GenerateParams(temperature=0.7, max_tokens=1500))
    logger.debug("llm generate completed: encounter_id=%s", encounter_id)

    # (4) 下書き永続化 + 監査ログ追記 (同一トランザクション内)
    now = datetime.now(tz=UTC)
    draft = RecordDraft(
        id=uuid4(),
        encounter_id=encounter_id,
        content=response.text,
        confidence=response.confidence,
        created_at=now,
        updated_at=now,
    )
    await draft_repo.add(draft)

    # 監査ログ: meta_json は PHI を含まない空オブジェクト
    audit = AuditLog(
        id=uuid4(),
        at=now,
        actor=_PLACEHOLDER_CLINICIAN_ID,
        action=AuditAction.DRAFT_CREATE,
        target_kind="record_draft",
        target_id=draft.id,
        meta_json="{}",
    )
    await audit_repo.append(audit)

    # PHI をログに書かない — id のみ記録する
    logger.info("record_draft created: id=%s encounter_id=%s", draft.id, encounter_id)
    return draft


async def find_draft_by_id(
    *,
    draft_id: UUID,
    draft_repo: RecordDraftRepository,
) -> RecordDraft:
    """ID でカルテ下書きを取得する。存在しない場合は DraftNotFound を raise する。

    content は PHI のためログに出力しない。
    """
    draft = await draft_repo.find_by_id(draft_id)
    if draft is None:
        logger.debug("record_draft not found")
        raise DraftNotFound
    return draft
