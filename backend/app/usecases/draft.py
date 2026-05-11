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

import json
import logging
from collections.abc import AsyncGenerator, Callable, Coroutine
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.domain.entities import AuditAction, AuditLog, RecordDraft
from app.domain.phi import short_id
from app.infrastructure.db.repositories import (
    AuditLogRepository,
    EncounterRepository,
    RecordDraftRepository,
)
from app.infrastructure.llm.client import LocalLLMClient
from app.infrastructure.llm.types import Chunk, GenerateParams
from app.usecases.errors import DraftNotFound, EncounterNotFound
from app.usecases.prompts import build_draft_prompt

logger = logging.getLogger(__name__)


async def generate_record_draft(
    *,
    clinical_input: str,
    encounter_id: UUID,
    clinician_id: UUID,
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
    logger.debug(
        "draft prompt built: encounter_id=%s length=%d",
        short_id(encounter_id),
        len(prompt),
    )

    # (3) LLM 呼び出し: InferenceError はキャッチせず伝播させる
    # PHI を含む clinical_input / response.text はログに書かない
    response = await llm.generate(prompt, GenerateParams(temperature=0.7, max_tokens=1500))
    logger.debug("llm generate completed: encounter_id=%s", short_id(encounter_id))

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
        actor=clinician_id,
        action=AuditAction.DRAFT_CREATE,
        target_kind="record_draft",
        target_id=draft.id,
        meta_json="{}",
    )
    await audit_repo.append(audit)

    # PHI をログに書かない — short_id で再識別リスクを低減する
    logger.info(
        "record_draft created: id=%s encounter_id=%s clinician_id=%s",
        short_id(draft.id),
        short_id(encounter_id),
        short_id(clinician_id),
    )
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


async def list_drafts_by_encounter(
    *,
    encounter_id: UUID,
    draft_repo: RecordDraftRepository,
) -> list[RecordDraft]:
    """受診に紐づく全下書きを created_at 降順で返す (BE-009)。

    受診に下書きが存在しない場合は空リストを返す (例外を raise しない)。
    受診の存在確認は行わない — 空リストが正しい答えであるため (list_finals_by_encounter と同方針)。
    content は PHI のためログに出力しない。encounter_id と件数のみ記録する。
    """
    drafts = await draft_repo.list_by_encounter(encounter_id)
    logger.debug(
        "list_drafts_by_encounter: encounter_id=%s count=%d",
        short_id(encounter_id),
        len(drafts),
    )
    return drafts


async def edit_record_draft(
    *,
    draft_id: UUID,
    content: str,
    clinician_id: UUID,
    draft_repo: RecordDraftRepository,
    audit_repo: AuditLogRepository,
) -> RecordDraft:
    """臨床医によるカルテ下書き編集を適用し、更新済みエンティティを返す。

    処理順序:
      1. 下書きの存在確認 (DraftNotFound を raise する可能性あり)
      2. RecordDraftRepository.update_content で本文と updated_at を更新
      3. AuditLog (DRAFT_UPDATE) を追記
      4. 更新後のエンティティを返す (同一トランザクション内)

    content は PHI のためログに出力しない。
    """
    # (1) 下書き存在確認
    draft = await draft_repo.find_by_id(draft_id)
    if draft is None:
        logger.debug("edit_record_draft aborted: draft not found")
        raise DraftNotFound

    # (2) 本文更新: UTC タイムスタンプはユースケースが所有する
    now = datetime.now(tz=UTC)
    await draft_repo.update_content(draft_id, content, now)

    # (3) 監査ログ追記: meta_json は PHI を含まない空オブジェクト
    audit = AuditLog(
        id=uuid4(),
        at=now,
        actor=clinician_id,
        action=AuditAction.DRAFT_UPDATE,
        target_kind="record_draft",
        target_id=draft_id,
        meta_json="{}",
    )
    await audit_repo.append(audit)

    # PHI をログに書かない — short_id で再識別リスクを低減する
    logger.info(
        "record_draft edited: id=%s clinician_id=%s",
        short_id(draft_id),
        short_id(clinician_id),
    )

    # (4) 更新後エンティティを再取得して返す (update_content は返り値を持たない)
    updated = await draft_repo.find_by_id(draft_id)
    # update_content の後は必ず行が存在するため None にはならない
    assert updated is not None
    return updated


async def stream_record_draft(
    *,
    clinical_input: str,
    encounter_id: UUID,
    clinician_id: UUID,
    llm: LocalLLMClient,
    encounter_repo: EncounterRepository,
    draft_repo: RecordDraftRepository,
    audit_repo: AuditLogRepository,
    session_commit: Callable[[], Coroutine[Any, Any, None]],
) -> AsyncGenerator[Chunk, None]:
    """AI によるカルテ下書きをストリーミング生成し、完了後に永続化する非同期ジェネレータ。

    処理順序:
      1. 受診の存在確認 (EncounterNotFound を raise する可能性あり — LLM 呼び出し前)
      2. プロンプト構築 (build_draft_prompt — 副作用なし)
      3. LLM ストリームから各チャンクを yield する。テキストをバッファに蓄積する。
      4. ストリーム完了後 (chunk.done is True)、RecordDraft + AuditLog を永続化。
      5. 最終チャンク: draft_id と confidence を含む "completion" チャンクを yield する。

    InferenceError は mid-stream でも伝播させる — ルーター側でエラー SSE イベントに変換する。
    content / clinical_input / chunk.text は PHI のためログに書かない。
    """
    # (1) 受診存在確認: LLM 呼び出し前に同期的に確認する
    encounter = await encounter_repo.find_by_id(encounter_id)
    if encounter is None:
        logger.debug("stream_record_draft aborted: encounter not found")
        raise EncounterNotFound

    # (2) プロンプト構築: clinical_input は PHI のため内容はログに書かない
    prompt = build_draft_prompt(clinical_input)
    logger.debug(
        "stream draft prompt built: encounter_id=%s length=%d",
        short_id(encounter_id),
        len(prompt),
    )

    # (3) LLM ストリーム: テキストをバッファに蓄積しながら各チャンクを呼び出し元に yield する
    # chunk.text / content は PHI のためログに書かない
    buffer: list[str] = []
    last_confidence: float | None = None

    async for chunk in llm.stream(prompt, GenerateParams(temperature=0.7, max_tokens=1500)):
        if chunk.text:
            buffer.append(chunk.text)
        if chunk.confidence is not None:
            last_confidence = chunk.confidence
        if not chunk.done:
            # 未完了チャンクをそのまま呼び出し元に返す
            yield chunk
        # done=True のチャンクは下記の永続化後に completion チャンクとして yield する

    # (4) ストリーム完了: draft + audit を永続化する (InferenceError なく完走した場合のみ)
    now = datetime.now(tz=UTC)
    assembled_content = "".join(buffer)
    draft = RecordDraft(
        id=uuid4(),
        encounter_id=encounter_id,
        content=assembled_content,
        confidence=last_confidence,
        created_at=now,
        updated_at=now,
    )
    await draft_repo.add(draft)

    # 監査ログ: meta_json は PHI を含まない空オブジェクト
    audit = AuditLog(
        id=uuid4(),
        at=now,
        actor=clinician_id,
        action=AuditAction.DRAFT_CREATE,
        target_kind="record_draft",
        target_id=draft.id,
        meta_json="{}",
    )
    await audit_repo.append(audit)

    # トランザクションコミット: ルーター DI から渡されたコミット関数を呼び出す
    await session_commit()

    # PHI をログに書かない — short_id で再識別リスクを低減する
    logger.info(
        "stream record_draft created: id=%s encounter_id=%s clinician_id=%s",
        short_id(draft.id),
        short_id(encounter_id),
        short_id(clinician_id),
    )

    # (5) クライアントが draft_id を参照できるよう completion チャンクを yield する
    # テキストには draft_id を JSON エンコードして埋め込む (SSE "complete" イベントのペイロード)
    completion_payload = json.dumps(
        {"draft_id": str(draft.id), "confidence": last_confidence},
        ensure_ascii=False,
    )
    yield Chunk(text=completion_payload, done=True, confidence=last_confidence)
