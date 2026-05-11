"""リポジトリ実装。永続化は全てここを経由する。

各リポジトリは:
  - ドメインエンティティを受け取り / 返す (ORM 行を呼び出し元に漏らさない)
  - PHI をログに書かない (PHI ルール §3)
  - usecases / interfaces 層から直接 SQL を書かせない
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import (
    AuditAction,
    AuditLog,
    Encounter,
    Patient,
    RecordDraft,
    RecordFinal,
)

from .models import (
    AuditActionORM,
    AuditLogORM,
    EncounterORM,
    PatientORM,
    RecordDraftORM,
    RecordFinalORM,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# マッパー関数: ORM → ドメインエンティティ
# ---------------------------------------------------------------------------


def _patient_to_domain(row: PatientORM) -> Patient:
    return Patient(
        id=row.id,
        mrn=row.mrn,
        family_name=row.family_name,
        given_name=row.given_name,
        date_of_birth=row.date_of_birth,
        created_at=row.created_at,
    )


def _encounter_to_domain(row: EncounterORM) -> Encounter:
    return Encounter(
        id=row.id,
        patient_id=row.patient_id,
        encountered_at=row.encountered_at,
        clinician_id=row.clinician_id,
        created_at=row.created_at,
    )


def _draft_to_domain(row: RecordDraftORM) -> RecordDraft:
    return RecordDraft(
        id=row.id,
        encounter_id=row.encounter_id,
        content=row.content,
        confidence=row.confidence,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _final_to_domain(row: RecordFinalORM) -> RecordFinal:
    return RecordFinal(
        id=row.id,
        encounter_id=row.encounter_id,
        content=row.content,
        confidence=row.confidence,
        clinician_id=row.clinician_id,
        predecessor_id=row.predecessor_id,
        created_at=row.created_at,
    )


def _audit_to_domain(row: AuditLogORM) -> AuditLog:
    return AuditLog(
        id=row.id,
        at=row.at,
        actor=row.actor,
        action=AuditAction(row.action.value),
        target_kind=row.target_kind,
        target_id=row.target_id,
        meta_json=row.meta_json,
    )


# ---------------------------------------------------------------------------
# PatientRepository
# ---------------------------------------------------------------------------


class PatientRepository:
    """患者エンティティのリポジトリ。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, patient: Patient) -> None:
        """患者を追加する。"""
        row = PatientORM(
            id=patient.id,
            mrn=patient.mrn,
            family_name=patient.family_name,
            given_name=patient.given_name,
            date_of_birth=patient.date_of_birth,
            created_at=patient.created_at,
        )
        self._session.add(row)
        # PHI をログに書かない — ID のみ記録する
        logger.debug("patient added: id=%s", patient.id)

    async def find_by_id(self, patient_id: UUID) -> Patient | None:
        """ID で患者を取得する。存在しない場合は None。"""
        result = await self._session.execute(select(PatientORM).where(PatientORM.id == patient_id))
        row = result.scalar_one_or_none()
        return _patient_to_domain(row) if row else None

    async def find_by_mrn(self, mrn: str) -> Patient | None:
        """診察番号で患者を取得する。存在しない場合は None。"""
        result = await self._session.execute(select(PatientORM).where(PatientORM.mrn == mrn))
        row = result.scalar_one_or_none()
        return _patient_to_domain(row) if row else None


# ---------------------------------------------------------------------------
# EncounterRepository
# ---------------------------------------------------------------------------


class EncounterRepository:
    """受診エンティティのリポジトリ。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, encounter: Encounter) -> None:
        """受診を追加する。"""
        row = EncounterORM(
            id=encounter.id,
            patient_id=encounter.patient_id,
            encountered_at=encounter.encountered_at,
            clinician_id=encounter.clinician_id,
            created_at=encounter.created_at,
        )
        self._session.add(row)
        logger.debug("encounter added: id=%s patient_id=%s", encounter.id, encounter.patient_id)

    async def find_by_id(self, encounter_id: UUID) -> Encounter | None:
        """ID で受診を取得する。存在しない場合は None。"""
        result = await self._session.execute(
            select(EncounterORM).where(EncounterORM.id == encounter_id)
        )
        row = result.scalar_one_or_none()
        return _encounter_to_domain(row) if row else None

    async def list_by_patient(self, patient_id: UUID) -> list[Encounter]:
        """患者 ID に紐づく全受診を取得する。"""
        result = await self._session.execute(
            select(EncounterORM)
            .where(EncounterORM.patient_id == patient_id)
            .order_by(EncounterORM.encountered_at.desc())
        )
        return [_encounter_to_domain(r) for r in result.scalars().all()]


# ---------------------------------------------------------------------------
# RecordDraftRepository
# ---------------------------------------------------------------------------


class RecordDraftRepository:
    """カルテ下書きリポジトリ。下書きは署名前なので更新を許容する。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, draft: RecordDraft) -> None:
        """下書きを追加する。"""
        row = RecordDraftORM(
            id=draft.id,
            encounter_id=draft.encounter_id,
            content=draft.content,
            confidence=draft.confidence,
            created_at=draft.created_at,
            updated_at=draft.updated_at,
        )
        self._session.add(row)
        logger.debug("record_draft added: id=%s", draft.id)

    async def find_by_id(self, draft_id: UUID) -> RecordDraft | None:
        """ID で下書きを取得する。存在しない場合は None。"""
        result = await self._session.execute(
            select(RecordDraftORM).where(RecordDraftORM.id == draft_id)
        )
        row = result.scalar_one_or_none()
        return _draft_to_domain(row) if row else None

    async def update_content(self, draft_id: UUID, content: str, updated_at: object) -> None:
        """下書きの本文と更新日時を更新する。臨床医の編集に対応する。"""
        result = await self._session.execute(
            select(RecordDraftORM).where(RecordDraftORM.id == draft_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise ValueError(f"record_draft not found: id={draft_id}")
        # PHI の content は直接ログに書かない
        row.content = content
        row.updated_at = updated_at  # type: ignore[assignment]
        logger.debug("record_draft updated: id=%s", draft_id)

    async def list_by_encounter(self, encounter_id: UUID) -> list[RecordDraft]:
        """受診 ID に紐づく全下書きを created_at 降順で返す (BE-009)。

        受診が存在しない場合は空リストを返す。受診の存在確認はユースケース層の責務。
        content は PHI のため encounter_id のみログに記録する。
        """
        result = await self._session.execute(
            select(RecordDraftORM)
            .where(RecordDraftORM.encounter_id == encounter_id)
            .order_by(RecordDraftORM.created_at.desc())
        )
        return [_draft_to_domain(r) for r in result.scalars().all()]


# ---------------------------------------------------------------------------
# RecordFinalRepository
# ---------------------------------------------------------------------------


class RecordFinalRepository:
    """確定カルテリポジトリ。

    イミュータビリティ保証:
      (a) models.py の before_flush イベントが UPDATE を拒否する
      (b) このリポジトリは update_* メソッドを定義しない
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, record: RecordFinal) -> None:
        """確定カルテを追加する。訂正版は predecessor_id を設定して add() する。"""
        row = RecordFinalORM(
            id=record.id,
            encounter_id=record.encounter_id,
            content=record.content,
            confidence=record.confidence,
            clinician_id=record.clinician_id,
            predecessor_id=record.predecessor_id,
            created_at=record.created_at,
        )
        self._session.add(row)
        logger.debug(
            "record_final added: id=%s predecessor_id=%s",
            record.id,
            record.predecessor_id,
        )

    async def find_by_id(self, record_id: UUID) -> RecordFinal | None:
        """ID で確定カルテを取得する。存在しない場合は None。"""
        result = await self._session.execute(
            select(RecordFinalORM).where(RecordFinalORM.id == record_id)
        )
        row = result.scalar_one_or_none()
        return _final_to_domain(row) if row else None

    async def find_by_encounter(self, encounter_id: UUID) -> RecordFinal | None:
        """受診 ID に紐づく最初の確定カルテを返す。存在しない場合は None。

        BE-007: 二重確定防止チェックに使用する。
        predecessor_id チェーンの深さは問わない — 1 件でも存在すれば確定済みとみなす。
        """
        result = await self._session.execute(
            select(RecordFinalORM).where(RecordFinalORM.encounter_id == encounter_id).limit(1)
        )
        row = result.scalar_one_or_none()
        return _final_to_domain(row) if row else None

    async def list_by_encounter(self, encounter_id: UUID) -> list[RecordFinal]:
        """受診 ID に紐づく全確定カルテを created_at 昇順で返す。

        BE-008: GET /encounters/{id}/finals および list_finals_by_encounter ユースケースに使用する。
        find_by_encounter (BE-007) は二重確定防止ガードとして引き続き使用する。
        受診が存在しない場合は空リストを返す。
        """
        result = await self._session.execute(
            select(RecordFinalORM)
            .where(RecordFinalORM.encounter_id == encounter_id)
            .order_by(RecordFinalORM.created_at.asc())
        )
        return [_final_to_domain(r) for r in result.scalars().all()]

    async def find_chain(self, record_id: UUID) -> list[RecordFinal]:
        """指定 ID から predecessor_id を辿って全前版を返す。

        返却リストは [最古版, ..., 指定版] の昇順。
        指定 ID 自身も含む。存在しない場合は空リスト。
        """
        chain: list[RecordFinal] = []
        current_id: UUID | None = record_id
        seen: set[UUID] = set()

        while current_id is not None:
            if current_id in seen:
                # 循環参照ガード (DB 制約で防がれるべきだが念のため)
                logger.warning("record_final chain cycle detected at id=%s", current_id)
                break
            seen.add(current_id)

            result = await self._session.execute(
                select(RecordFinalORM).where(RecordFinalORM.id == current_id)
            )
            row = result.scalar_one_or_none()
            if row is None:
                break
            chain.append(_final_to_domain(row))
            current_id = row.predecessor_id

        # 辿った順は新→旧なので逆順にする
        chain.reverse()
        return chain


# ---------------------------------------------------------------------------
# AuditLogRepository
# ---------------------------------------------------------------------------


class AuditLogRepository:
    """監査ログリポジトリ。append-only。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(self, entry: AuditLog) -> None:
        """監査ログを追加する。"""
        row = AuditLogORM(
            id=entry.id,
            at=entry.at,
            actor=entry.actor,
            action=AuditActionORM(entry.action.value),
            target_kind=entry.target_kind,
            target_id=entry.target_id,
            meta_json=entry.meta_json,
        )
        self._session.add(row)
        # PHI を含む可能性があるため target_id と action のみ記録する
        logger.debug("audit_log appended: action=%s target_id=%s", entry.action, entry.target_id)

    async def list_by_target(self, target_kind: str, target_id: UUID) -> list[AuditLog]:
        """対象エンティティに関する監査ログを時系列順で返す。"""
        result = await self._session.execute(
            select(AuditLogORM)
            .where(
                AuditLogORM.target_kind == target_kind,
                AuditLogORM.target_id == target_id,
            )
            .order_by(AuditLogORM.at.asc())
        )
        return [_audit_to_domain(r) for r in result.scalars().all()]
