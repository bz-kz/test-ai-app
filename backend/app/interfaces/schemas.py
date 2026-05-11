"""インタフェース層の共通 Pydantic モデル。

全エンドポイントが共有するリクエスト/レスポンス型を定義する。
PHI を含む可能性のあるフィールドはここで宣言せず、
各ドメイン固有スキーマファイルで適切にマスク処理を施す。
"""

from __future__ import annotations

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """正規化エラーエンベロープ。

    全例外ハンドラが返す共通形式。
    `code` はクライアントが機械的に判別できる安定した識別子。
    `message` は英語の人間向けテキストで PHI を含まない。
    """

    code: str
    message: str
