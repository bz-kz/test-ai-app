"""PHI マスクユーティリティ。

ドメイン層の純粋関数。インフラ・ユースケース・インタフェース層の全層から参照可能。
ログ出力前に PHI を含む可能性のある文字列をマスクするために使う。
"""

from __future__ import annotations


def mask_phi(value: str) -> str:
    """ログ出力前に PHI を含む可能性のある文字列をマスクする。

    プロンプトや応答本文をそのままログに書かないために使う。
    先頭 8 文字のみ保持し、残りを長さ情報付きでマスクする。
    短い文字列でも先頭 8 文字を超える部分は必ずマスクされる。
    """
    if not value:
        return value
    # 常に先頭 8 文字だけを診断用に残し、それ以降はマスクする
    preview_len = min(8, len(value))
    masked_len = len(value) - preview_len
    return value[:preview_len] + f"...[masked {masked_len} chars]"
