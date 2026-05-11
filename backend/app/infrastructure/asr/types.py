"""ASR インフラ層の共通型定義。"""

from __future__ import annotations

from dataclasses import dataclass

# mask_phi はドメイン層で定義された純粋関数。
from app.domain.phi import mask_phi

__all__ = ["AudioPayload", "TranscribeParams", "TranscribeResponse", "mask_phi"]


@dataclass(frozen=True)
class AudioPayload:
    """transcribe() に渡す音声データ。

    audio_bytes は PHI であるため、ログに書かないこと。
    """

    audio_bytes: bytes
    content_type: str


@dataclass(frozen=True)
class TranscribeParams:
    """transcribe() に渡す文字起こしパラメータ。"""

    language: str = "ja"


@dataclass(frozen=True)
class TranscribeResponse:
    """transcribe() の完全レスポンス。

    text は PHI であるため、ログに書く際は mask_phi() を使うこと。
    """

    text: str
    # ASR バックエンドが duration を返す場合のみ付与される
    duration_seconds: float | None = None
