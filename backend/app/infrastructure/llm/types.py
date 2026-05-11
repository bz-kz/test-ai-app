"""LLM インフラ層の共通型定義。ドメイン層への依存を持たない。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GenerateParams:
    """generate() / stream() に渡す推論パラメータ。"""

    temperature: float = 0.7
    max_tokens: int = 1500
    # 将来の拡張用に追加フィールドを許容する
    extra: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class GenerateResponse:
    """generate() の完全レスポンス。"""

    text: str
    # モデルが信頼度を返す場合のみ付与される
    confidence: float | None = None


@dataclass(frozen=True)
class Chunk:
    """stream() が yield する単一チャンク。"""

    text: str
    done: bool
    confidence: float | None = None


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
