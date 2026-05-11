"""LocalASRClient プロトコル定義。具体実装に依存しない契約を定める。"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .types import AudioPayload, TranscribeParams, TranscribeResponse


@runtime_checkable
class LocalASRClient(Protocol):
    """ASR バックエンドへの統一インタフェース。

    WhisperCppLocalASRClient（本番）と FakeLocalASRClient（テスト）が実装する。
    usecases 層はこのプロトコルに対してのみ依存する。
    """

    async def transcribe(
        self,
        audio: AudioPayload,
        params: TranscribeParams | None = None,
    ) -> TranscribeResponse:
        """音声データを送信して文字起こし結果を返す。

        非200 またはタイムアウト時は ASRError を送出する。
        音声バイト列・ファイル名・トランスクリプトはログに書かない。
        """
        ...

    async def ping(self) -> bool:
        """ASR サービスへの到達可能性を確認する。

        到達可能なら True、到達不能なら False を返す（例外を送出しない）。
        """
        ...
