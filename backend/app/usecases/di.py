"""ユースケース層の FastAPI DI サーフェス。

interfaces 層はここからのみ依存性を取得する。
infrastructure 層を直接参照しない。
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable, Coroutine
from datetime import date, datetime
from typing import Any
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Encounter, Patient, RecordDraft, RecordFinal
from app.infrastructure.db.engine import get_session
from app.infrastructure.db.repositories import (
    AuditLogRepository,
    EncounterRepository,
    PatientRepository,
    RecordDraftRepository,
    RecordFinalRepository,
)
from app.infrastructure.llm import make_llm_client
from app.infrastructure.llm.client import LocalLLMClient
from app.usecases.draft import edit_record_draft, find_draft_by_id, generate_record_draft
from app.usecases.encounter import (
    create_encounter,
    find_encounter_by_id,
    list_encounters_by_patient,
)
from app.usecases.final import (
    correct_record_final,
    finalize_draft_to_record_final,
    find_chain_for_final,
    find_final_by_id,
    list_finals_by_encounter,
)
from app.usecases.patient import create_patient, find_patient_by_id, find_patient_by_mrn

# ---------------------------------------------------------------------------
# シングルトン LLM クライアント
# リクエストごとに新しいインスタンスを生成しないようにモジュールレベルでキャッシュする。
# (BE-003 セキュリティレビューの [ADVICE] への対応)
# ---------------------------------------------------------------------------

_llm_client_instance: LocalLLMClient | None = None


def get_llm_client() -> LocalLLMClient:
    """シングルトン LLM クライアントを返す FastAPI 依存関数。

    テスト時は app.dependency_overrides[get_llm_client] で FakeLocalLLMClient に差し替える。
    本番では infrastructure 層のファクトリが生成したクライアントをキャッシュして再利用する。
    """
    global _llm_client_instance  # noqa: PLW0603
    if _llm_client_instance is None:
        # 具体実装の生成は infrastructure 層のファクトリに委譲する
        _llm_client_instance = make_llm_client()
    return _llm_client_instance


# ---------------------------------------------------------------------------
# セッション依存 (usecases.di 経由でのみ interfaces 層に公開する)
# ---------------------------------------------------------------------------


async def _get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI Depends 経由でセッションを提供する (infrastructure エンジンをラップ)。"""
    async for session in get_session():
        yield session


# ---------------------------------------------------------------------------
# ユースケースファクトリ型エイリアス
# ---------------------------------------------------------------------------

CreatePatientCallable = Callable[
    [str, str, str, date],
    Coroutine[Any, Any, Patient],
]

FindPatientByIdCallable = Callable[
    [UUID],
    Coroutine[Any, Any, Patient | None],
]

FindPatientByMrnCallable = Callable[
    [str],
    Coroutine[Any, Any, Patient | None],
]


# ---------------------------------------------------------------------------
# ユースケースファクトリ依存
# interfaces 層はこれらを Depends() で取得し、呼び出す。
# ---------------------------------------------------------------------------


def make_create_patient(
    session: AsyncSession = Depends(_get_db_session),
) -> CreatePatientCallable:
    """create_patient ユースケースをセッション付きでクロージャとして返す。"""
    patient_repo = PatientRepository(session)
    audit_repo = AuditLogRepository(session)

    async def _create(
        mrn: str,
        family_name: str,
        given_name: str,
        date_of_birth: date,
    ) -> Patient:
        patient = await create_patient(
            mrn=mrn,
            family_name=family_name,
            given_name=given_name,
            date_of_birth=date_of_birth,
            patient_repo=patient_repo,
            audit_repo=audit_repo,
        )
        await session.commit()
        return patient

    return _create


def make_find_patient_by_id(
    session: AsyncSession = Depends(_get_db_session),
) -> FindPatientByIdCallable:
    """find_patient_by_id ユースケースをセッション付きでクロージャとして返す。"""
    patient_repo = PatientRepository(session)

    async def _find(patient_id: UUID) -> Patient | None:
        return await find_patient_by_id(
            patient_id=patient_id,
            patient_repo=patient_repo,
        )

    return _find


def make_find_patient_by_mrn(
    session: AsyncSession = Depends(_get_db_session),
) -> FindPatientByMrnCallable:
    """find_patient_by_mrn ユースケースをセッション付きでクロージャとして返す。"""
    patient_repo = PatientRepository(session)

    async def _find(mrn: str) -> Patient | None:
        return await find_patient_by_mrn(
            mrn=mrn,
            patient_repo=patient_repo,
        )

    return _find


# ---------------------------------------------------------------------------
# 受診ユースケースファクトリ型エイリアス
# ---------------------------------------------------------------------------

CreateEncounterCallable = Callable[
    [UUID, datetime, UUID],
    Coroutine[Any, Any, Encounter],
]

FindEncounterByIdCallable = Callable[
    [UUID],
    Coroutine[Any, Any, Encounter],
]

ListEncountersByPatientCallable = Callable[
    [UUID],
    Coroutine[Any, Any, list[Encounter]],
]


# ---------------------------------------------------------------------------
# 受診ユースケースファクトリ依存
# ---------------------------------------------------------------------------


def make_create_encounter(
    session: AsyncSession = Depends(_get_db_session),
) -> CreateEncounterCallable:
    """create_encounter ユースケースをセッション付きでクロージャとして返す。"""
    patient_repo = PatientRepository(session)
    encounter_repo = EncounterRepository(session)
    audit_repo = AuditLogRepository(session)

    async def _create(
        patient_id: UUID,
        encountered_at: datetime,
        clinician_id: UUID,
    ) -> Encounter:
        encounter = await create_encounter(
            patient_id=patient_id,
            encountered_at=encountered_at,
            clinician_id=clinician_id,
            patient_repo=patient_repo,
            encounter_repo=encounter_repo,
            audit_repo=audit_repo,
        )
        await session.commit()
        return encounter

    return _create


def make_find_encounter_by_id(
    session: AsyncSession = Depends(_get_db_session),
) -> FindEncounterByIdCallable:
    """find_encounter_by_id ユースケースをセッション付きでクロージャとして返す。"""
    encounter_repo = EncounterRepository(session)

    async def _find(encounter_id: UUID) -> Encounter:
        return await find_encounter_by_id(
            encounter_id=encounter_id,
            encounter_repo=encounter_repo,
        )

    return _find


def make_list_encounters_by_patient(
    session: AsyncSession = Depends(_get_db_session),
) -> ListEncountersByPatientCallable:
    """list_encounters_by_patient ユースケースをセッション付きでクロージャとして返す。"""
    patient_repo = PatientRepository(session)
    encounter_repo = EncounterRepository(session)

    async def _list(patient_id: UUID) -> list[Encounter]:
        return await list_encounters_by_patient(
            patient_id=patient_id,
            patient_repo=patient_repo,
            encounter_repo=encounter_repo,
        )

    return _list


# ---------------------------------------------------------------------------
# カルテ下書きユースケースファクトリ型エイリアス
# ---------------------------------------------------------------------------

GenerateRecordDraftCallable = Callable[
    [str, UUID],
    Coroutine[Any, Any, RecordDraft],
]

FindDraftByIdCallable = Callable[
    [UUID],
    Coroutine[Any, Any, RecordDraft],
]


# ---------------------------------------------------------------------------
# カルテ下書きユースケースファクトリ依存
# ---------------------------------------------------------------------------


def make_generate_record_draft(
    session: AsyncSession = Depends(_get_db_session),
    llm: LocalLLMClient = Depends(get_llm_client),
) -> GenerateRecordDraftCallable:
    """generate_record_draft ユースケースをセッション + LLM クライアント付きでクロージャとして返す。

    LLM クライアントは get_llm_client 依存関数から取得するシングルトン。
    テスト時は app.dependency_overrides[get_llm_client] で差し替える。
    """
    encounter_repo = EncounterRepository(session)
    draft_repo = RecordDraftRepository(session)
    audit_repo = AuditLogRepository(session)

    async def _generate(clinical_input: str, encounter_id: UUID) -> RecordDraft:
        draft = await generate_record_draft(
            clinical_input=clinical_input,
            encounter_id=encounter_id,
            llm=llm,
            encounter_repo=encounter_repo,
            draft_repo=draft_repo,
            audit_repo=audit_repo,
        )
        await session.commit()
        return draft

    return _generate


def make_find_draft_by_id(
    session: AsyncSession = Depends(_get_db_session),
) -> FindDraftByIdCallable:
    """find_draft_by_id ユースケースをセッション付きでクロージャとして返す。"""
    draft_repo = RecordDraftRepository(session)

    async def _find(draft_id: UUID) -> RecordDraft:
        return await find_draft_by_id(
            draft_id=draft_id,
            draft_repo=draft_repo,
        )

    return _find


# ---------------------------------------------------------------------------
# 下書き編集ユースケースファクトリ型エイリアス
# ---------------------------------------------------------------------------

EditRecordDraftCallable = Callable[
    [UUID, str, UUID],
    Coroutine[Any, Any, RecordDraft],
]


# ---------------------------------------------------------------------------
# 確定カルテユースケースファクトリ型エイリアス
# ---------------------------------------------------------------------------

FinalizeDraftCallable = Callable[
    [UUID, UUID],
    Coroutine[Any, Any, RecordFinal],
]

FindFinalByIdCallable = Callable[
    [UUID],
    Coroutine[Any, Any, RecordFinal],
]

CorrectRecordFinalCallable = Callable[
    [UUID, str, UUID],
    Coroutine[Any, Any, RecordFinal],
]

ListFinalsByEncounterCallable = Callable[
    [UUID],
    Coroutine[Any, Any, list[RecordFinal]],
]

FindChainForFinalCallable = Callable[
    [UUID],
    Coroutine[Any, Any, list[RecordFinal]],
]


# ---------------------------------------------------------------------------
# 下書き編集ユースケースファクトリ依存
# ---------------------------------------------------------------------------


def make_edit_record_draft(
    session: AsyncSession = Depends(_get_db_session),
) -> EditRecordDraftCallable:
    """edit_record_draft ユースケースをセッション付きでクロージャとして返す。"""
    draft_repo = RecordDraftRepository(session)
    audit_repo = AuditLogRepository(session)

    async def _edit(draft_id: UUID, content: str, clinician_id: UUID) -> RecordDraft:
        draft = await edit_record_draft(
            draft_id=draft_id,
            content=content,
            clinician_id=clinician_id,
            draft_repo=draft_repo,
            audit_repo=audit_repo,
        )
        await session.commit()
        return draft

    return _edit


# ---------------------------------------------------------------------------
# 確定カルテユースケースファクトリ依存
# ---------------------------------------------------------------------------


def make_finalize_draft_to_record_final(
    session: AsyncSession = Depends(_get_db_session),
) -> FinalizeDraftCallable:
    """finalize_draft_to_record_final ユースケースをセッション付きでクロージャとして返す。"""
    draft_repo = RecordDraftRepository(session)
    final_repo = RecordFinalRepository(session)
    audit_repo = AuditLogRepository(session)

    async def _finalize(draft_id: UUID, clinician_id: UUID) -> RecordFinal:
        final = await finalize_draft_to_record_final(
            draft_id=draft_id,
            clinician_id=clinician_id,
            draft_repo=draft_repo,
            final_repo=final_repo,
            audit_repo=audit_repo,
        )
        await session.commit()
        return final

    return _finalize


def make_find_final_by_id(
    session: AsyncSession = Depends(_get_db_session),
) -> FindFinalByIdCallable:
    """find_final_by_id ユースケースをセッション付きでクロージャとして返す。"""
    final_repo = RecordFinalRepository(session)

    async def _find(final_id: UUID) -> RecordFinal:
        return await find_final_by_id(
            final_id=final_id,
            final_repo=final_repo,
        )

    return _find


def make_correct_record_final(
    session: AsyncSession = Depends(_get_db_session),
) -> CorrectRecordFinalCallable:
    """correct_record_final ユースケースをセッション付きでクロージャとして返す (BE-008)。"""
    final_repo = RecordFinalRepository(session)
    audit_repo = AuditLogRepository(session)

    async def _correct(source_final_id: UUID, content: str, clinician_id: UUID) -> RecordFinal:
        new_final = await correct_record_final(
            source_final_id=source_final_id,
            content=content,
            clinician_id=clinician_id,
            final_repo=final_repo,
            audit_repo=audit_repo,
        )
        await session.commit()
        return new_final

    return _correct


def make_list_finals_by_encounter(
    session: AsyncSession = Depends(_get_db_session),
) -> ListFinalsByEncounterCallable:
    """list_finals_by_encounter ユースケースをセッション付きでクロージャとして返す (BE-008)。"""
    final_repo = RecordFinalRepository(session)

    async def _list(encounter_id: UUID) -> list[RecordFinal]:
        return await list_finals_by_encounter(
            encounter_id=encounter_id,
            final_repo=final_repo,
        )

    return _list


def make_find_chain_for_final(
    session: AsyncSession = Depends(_get_db_session),
) -> FindChainForFinalCallable:
    """find_chain_for_final ユースケースをセッション付きでクロージャとして返す (BE-008)。"""
    final_repo = RecordFinalRepository(session)

    async def _find_chain(final_id: UUID) -> list[RecordFinal]:
        return await find_chain_for_final(
            final_id=final_id,
            final_repo=final_repo,
        )

    return _find_chain
