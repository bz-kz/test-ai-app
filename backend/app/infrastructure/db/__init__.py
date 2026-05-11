"""DB インフラ層の公開 API。

外部から使用するシンボル:
- get_session       : FastAPI 依存注入用の非同期セッションファクトリ
- Base              : SQLAlchemy DeclarativeBase
- engine            : 非同期エンジン (テスト・マイグレーション用)
- PhiLoggingFilter  : ログから PHI カラム値を除去するフィルタ
- PatientRepository
- EncounterRepository
- RecordDraftRepository
- RecordFinalRepository
- AuditLogRepository
"""

from .engine import Base, engine, get_session
from .logging_filter import PhiLoggingFilter
from .repositories import (
    AuditLogRepository,
    EncounterRepository,
    PatientRepository,
    RecordDraftRepository,
    RecordFinalRepository,
)

__all__ = [
    "Base",
    "engine",
    "get_session",
    "PhiLoggingFilter",
    "PatientRepository",
    "EncounterRepository",
    "RecordDraftRepository",
    "RecordFinalRepository",
    "AuditLogRepository",
]
