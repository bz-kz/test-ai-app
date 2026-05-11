"""受診ユースケース。

受診の作成・取得・一覧を担当する。インフラ層リポジトリを経由し、直接 SQL を書かない。
interfaces 層はインポートしない (DDD 方向: usecases → infrastructure → domain)。

クロスエンティティ検証:
  create_encounter は patient_id の存在確認と encounter INSERT を同一トランザクション内で行う。
  患者が存在しない場合は PatientNotFound を raise し、encounter 行は書かない。
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domain.entities import AuditAction, AuditLog, Encounter
from app.infrastructure.db.repositories import (
    AuditLogRepository,
    EncounterRepository,
    PatientRepository,
)
from app.usecases.errors import EncounterNotFound, PatientNotFound

logger = logging.getLogger(__name__)


async def create_encounter(
    *,
    patient_id: UUID,
    encountered_at: datetime,
    clinician_id: UUID,
    patient_repo: PatientRepository,
    encounter_repo: EncounterRepository,
    audit_repo: AuditLogRepository,
) -> Encounter:
    """受診を新規作成し、監査ログを記録する。

    患者の存在確認と encounter INSERT を同一トランザクション内で実行する。
    患者が存在しない場合は PatientNotFound を raise し、INSERT は行わない。
    PHI は encounter エンティティ内に保持するが、ログには出力しない。
    """
    # 患者存在確認: 存在しない場合は PatientNotFound を raise する
    patient = await patient_repo.find_by_id(patient_id)
    if patient is None:
        # patient_id は PHI 単独ではないが UUID をエラーメッセージに含めない
        logger.debug("encounter creation aborted: patient not found")
        raise PatientNotFound

    now = datetime.now(tz=UTC)
    encounter = Encounter(
        id=uuid4(),
        patient_id=patient_id,
        encountered_at=encountered_at,
        clinician_id=clinician_id,
        created_at=now,
    )
    await encounter_repo.add(encounter)

    # 監査ログ: meta_json は PHI を含まない空オブジェクト; patient_id は含めない
    audit = AuditLog(
        id=uuid4(),
        at=now,
        actor=clinician_id,
        action=AuditAction.ENCOUNTER_CREATE,
        target_kind="encounter",
        target_id=encounter.id,
        meta_json="{}",
    )
    await audit_repo.append(audit)

    # PHI をログに書かない — id のみ記録する
    logger.info("encounter created: id=%s", encounter.id)
    return encounter


async def find_encounter_by_id(
    *,
    encounter_id: UUID,
    encounter_repo: EncounterRepository,
) -> Encounter:
    """ID で受診を取得する。存在しない場合は EncounterNotFound を raise する。"""
    encounter = await encounter_repo.find_by_id(encounter_id)
    if encounter is None:
        logger.debug("encounter not found: id=%s", encounter_id)
        raise EncounterNotFound
    return encounter


async def list_encounters_by_patient(
    *,
    patient_id: UUID,
    patient_repo: PatientRepository,
    encounter_repo: EncounterRepository,
) -> list[Encounter]:
    """患者に紐づく全受診を encountered_at 降順で返す。

    患者が存在しない場合は PatientNotFound を raise する。
    患者が存在するが受診がない場合は空リストを返す。
    """
    # 患者存在確認: 存在しない患者への一覧要求は 404 にする
    patient = await patient_repo.find_by_id(patient_id)
    if patient is None:
        logger.debug("encounter list aborted: patient not found")
        raise PatientNotFound

    encounters = await encounter_repo.list_by_patient(patient_id)
    logger.debug("encounter list: patient_id=%s count=%d", patient_id, len(encounters))
    return encounters
