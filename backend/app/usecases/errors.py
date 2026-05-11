"""ユースケース層の例外定義。

ドメイン違反や業務ルール違反を表す例外。
interfaces 層はここで定義された例外を受け取り、HTTP エラーに変換する。
"""

from __future__ import annotations

# レイヤー規則のシーム: interfaces は infrastructure を直接参照できないため、
# InferenceError / ASRError をここで再エクスポートする。interfaces はこのモジュール経由で取得する。
from app.infrastructure.asr.errors import ASRError
from app.infrastructure.llm.errors import InferenceError

__all__ = [
    "ASRError",
    "DraftNotFound",
    "EncounterAlreadyFinalized",
    "EncounterNotFound",
    "FinalNotFound",
    "InferenceError",
    "MRNConflict",
    "PatientNotFound",
]


class MRNConflict(Exception):
    """同一 MRN の患者がすでに存在する場合に raise する。

    PHI (MRN 値) を属性として保持しない。
    インターフェース層が 409 に変換する。
    """


class PatientNotFound(Exception):
    """指定された patient_id の患者が存在しない場合に raise する。

    UUID 値を属性として保持しない (エラーメッセージへの漏洩防止)。
    インターフェース層が 404 に変換する。
    """


class EncounterNotFound(Exception):
    """指定された encounter_id の受診が存在しない場合に raise する。

    UUID 値を属性として保持しない (エラーメッセージへの漏洩防止)。
    インターフェース層が 404 に変換する。
    """


class DraftNotFound(Exception):
    """指定された draft_id のカルテ下書きが存在しない場合に raise する。

    UUID 値を属性として保持しない (エラーメッセージへの漏洩防止)。
    インターフェース層が 404 に変換する。
    """


class FinalNotFound(Exception):
    """指定された final_id の確定カルテが存在しない場合に raise する。

    UUID 値を属性として保持しない (エラーメッセージへの漏洩防止)。
    インターフェース層が 404 に変換する。
    """


class EncounterAlreadyFinalized(Exception):
    """指定受診にすでに確定カルテが存在する場合に raise する。

    UUID 値・PHI を属性として保持しない (エラーメッセージへの漏洩防止)。
    インターフェース層が 409 に変換する。
    訂正版の作成 (predecessor_id チェーン) は BE-008 のスコープ。
    """
