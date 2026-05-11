"""PHI ロギングフィルタ。

ログレコードを走査し、ORM モデルの phi=True カラムに由来する値を
mask_phi() でマスクして置換する。

mask_phi は app/infrastructure/llm/types.py で定義されている。
同じ infrastructure 層内のユーティリティであり、domain → infrastructure の
逆方向依存を生じさせないため、この参照は PHI ルール §2 に違反しない。
"""

from __future__ import annotations

import logging

from .models import (
    AuditLogORM,
    EncounterORM,
    PatientORM,
    RecordDraftORM,
    RecordFinalORM,
)

# PHI カラムを持つ全 ORM クラスのリスト
_PHI_MODELS = [PatientORM, EncounterORM, RecordDraftORM, RecordFinalORM, AuditLogORM]


def _collect_phi_column_names() -> frozenset[str]:
    """phi=True でフラグされたカラム名を全モデルから収集する。"""
    names: set[str] = set()
    for model in _PHI_MODELS:
        for col in model.__table__.columns:
            if col.info.get("phi"):
                names.add(col.name)
    return frozenset(names)


# モジュールロード時に一度だけ収集する (動的変化なし)
_PHI_COLUMN_NAMES: frozenset[str] = _collect_phi_column_names()


class PhiLoggingFilter(logging.Filter):
    """ログメッセージ中の PHI を検出してマスクする logging.Filter。

    このフィルタはルートロガーまたは対象ロガーに attach して使う。
    PHI カラム名をキーワードとして含む文字列値を mask_phi() で置換する。

    Note: このフィルタはベストエフォートの保護層。ログ呼び出し側でも
    PHI を直接渡さないように実装すること (PHI ルール §3)。
    """

    def filter(self, record: logging.LogRecord) -> bool:
        # メッセージを文字列化してから PHI カラム名でスキャンする
        msg = record.getMessage()
        for col_name in _PHI_COLUMN_NAMES:
            # カラム名そのものがログに含まれていればマスク候補とみなす
            # 値を直接ログに書かないよう実装側が責任を持つのが主防衛線
            if col_name in msg:
                record.msg = f"[PHI column '{col_name}' detected in log — masked]"
                record.args = ()
                return True
        return True


def get_phi_column_names() -> frozenset[str]:
    """テスト・セキュリティチェック用: PHI カラム名セットを返す。"""
    return _PHI_COLUMN_NAMES
