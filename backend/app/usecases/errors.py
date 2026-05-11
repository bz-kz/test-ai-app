"""ユースケース層の例外定義。

ドメイン違反や業務ルール違反を表す例外。
interfaces 層はここで定義された例外を受け取り、HTTP エラーに変換する。
"""

from __future__ import annotations


class MRNConflict(Exception):
    """同一 MRN の患者がすでに存在する場合に raise する。

    PHI (MRN 値) を属性として保持しない。
    インターフェース層が 409 に変換する。
    """
