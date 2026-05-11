"""患者ユースケース。

患者の作成・取得を担当する。インフラ層リポジトリを経由し、直接 SQL を書かない。
interfaces 層はインポートしない (DDD 方向: usecases → infrastructure → domain)。
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from app.domain.entities import AuditAction, AuditLog, Patient
from app.domain.phi import mask_phi
from app.infrastructure.db.repositories import AuditLogRepository, PatientRepository
from app.usecases.errors import MRNConflict

logger = logging.getLogger(__name__)

# 認証機能が未実装のため、プレースホルダーとして固定の臨床医 UUID を使用する。
# 将来の auth Block でリクエストコンテキストから取得する UUID に置き換えること。
_PLACEHOLDER_CLINICIAN_ID = UUID("00000000-0000-0000-0000-000000000001")


async def create_patient(
    *,
    mrn: str,
    family_name: str,
    given_name: str,
    date_of_birth: date,
    patient_repo: PatientRepository,
    audit_repo: AuditLogRepository,
) -> Patient:
    """患者を新規作成し、監査ログを記録する。

    MRN 重複の場合は MRNConflict を raise する。
    同じトランザクションで patient INSERT と audit_log INSERT を行う。
    PHI は患者エンティティ内に保持するが、ログには出力しない。
    """
    # MRN 重複チェック: ユースケース内で完結させ、interfaces 層に露出しない
    existing = await patient_repo.find_by_mrn(mrn)
    if existing is not None:
        raise MRNConflict

    # date → datetime(UTC midnight) に変換する (domain entity は datetime 型)
    dob_dt = datetime(date_of_birth.year, date_of_birth.month, date_of_birth.day, tzinfo=UTC)

    now = datetime.now(tz=UTC)
    patient = Patient(
        id=uuid4(),
        mrn=mrn,
        family_name=family_name,
        given_name=given_name,
        date_of_birth=dob_dt,
        created_at=now,
    )
    await patient_repo.add(patient)

    audit = AuditLog(
        id=uuid4(),
        at=now,
        actor=_PLACEHOLDER_CLINICIAN_ID,
        action=AuditAction.PATIENT_CREATE,
        target_kind="patient",
        target_id=patient.id,
        # PHI を含まないメタデータのみ記録する
        meta_json="{}",
    )
    await audit_repo.append(audit)

    # PHI をログに書かない — id のみ記録する
    logger.info("patient created: id=%s", patient.id)
    return patient


async def find_patient_by_id(
    *,
    patient_id: UUID,
    patient_repo: PatientRepository,
) -> Patient | None:
    """ID で患者を取得する。存在しない場合は None。

    PHI を含む検索条件 (patient_id は UUID で PHI ではない) だが
    結果の PHI フィールドはログに出力しない。
    """
    patient = await patient_repo.find_by_id(patient_id)
    if patient is None:
        logger.debug("patient not found: id=%s", patient_id)
    return patient


async def find_patient_by_mrn(
    *,
    mrn: str,
    patient_repo: PatientRepository,
) -> Patient | None:
    """MRN で患者を取得する。存在しない場合は None。

    MRN は PHI のためログに出力しない。
    """
    patient = await patient_repo.find_by_mrn(mrn)
    if patient is None:
        # MRN は PHI のためマスクしてからログに書く
        logger.debug("patient not found: mrn=%s", mask_phi(mrn))
    return patient
