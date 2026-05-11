"""LLM インフラ層の共通型定義。

mask_phi はドメイン層 (app.domain.phi) で定義し、ここで再エクスポートする。
これにより他の infrastructure モジュールが従来どおり types から import できる。
"""

from __future__ import annotations

from dataclasses import dataclass, field

# mask_phi はドメイン層で定義された純粋関数。再エクスポートして後方互換を維持する。
from app.domain.phi import mask_phi

__all__ = ["Chunk", "GenerateParams", "GenerateResponse", "mask_phi"]


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
