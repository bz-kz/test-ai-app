"""LocalLLMClient プロトコル定義。具体実装に依存しない契約を定める。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from .types import Chunk, GenerateParams, GenerateResponse


@runtime_checkable
class LocalLLMClient(Protocol):
    """LLM バックエンドへの統一インタフェース。

    OllamaLocalLLMClient（本番）と FakeLocalLLMClient（テスト）が実装する。
    usecases 層はこのプロトコルに対してのみ依存する。
    """

    async def generate(
        self,
        prompt: str,
        params: GenerateParams | None = None,
    ) -> GenerateResponse:
        """プロンプトを送信して完全な応答を返す（非ストリーミング）。

        非200 またはタイムアウト時は InferenceError を送出する。
        """
        ...

    def stream(
        self,
        prompt: str,
        params: GenerateParams | None = None,
    ) -> AsyncIterator[Chunk]:
        """プロンプトを送信してチャンクを非同期イテレータとして返す。

        エンドツーエンドのタイムアウトは LLM_TIMEOUT_S × 2 を上限とする。
        非200 またはタイムアウト時は InferenceError を送出する。
        """
        ...

    async def ping(self) -> bool:
        """LLM サービスへの到達可能性を確認する。

        /health エンドポイントから httpx を直接使わずに呼ぶためのメソッド。
        到達可能なら True、到達不能なら False を返す（例外を送出しない）。
        """
        ...
