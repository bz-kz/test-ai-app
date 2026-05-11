"""ASR 層の例外定義。音声バイト列・ファイル名・文字起こし結果は __str__ / __repr__ に含まない。"""

from __future__ import annotations

from .types import mask_phi


class ASRError(Exception):
    """ASR 呼び出しの失敗を表す型付き例外。

    raw_audio_len は保持するが音声バイト列・トランスクリプト本文は
    __str__ / __repr__ には出力しない。
    InferenceError と同じ設計規律を適用する (BE-001 precedent)。
    """

    def __init__(
        self,
        message: str,
        *,
        audio_length: int | None = None,
        status_code: int | None = None,
        timeout: bool = False,
    ) -> None:
        # 音声長のみ保持し、バイト列そのものは保持しない
        self._audio_length = audio_length
        self.status_code = status_code
        self.timeout = timeout
        # マスク済みコンテキストをメッセージに付与する
        _ctx = (
            mask_phi(f"audio_length={audio_length}") if audio_length is not None else "<no audio>"
        )
        self.masked_context = f"{message} | context: {_ctx}"
        # 親クラスには安全なメッセージのみ渡す
        super().__init__(self.masked_context)

    def __str__(self) -> str:
        # 音声バイト列・トランスクリプトを含まない安全な表現を返す
        return self.masked_context

    def __repr__(self) -> str:
        # 音声バイト列・トランスクリプトを含まない安全な表現を返す
        status = f", status_code={self.status_code}" if self.status_code is not None else ""
        timeout = ", timeout=True" if self.timeout else ""
        return f"ASRError({self.masked_context!r}{status}{timeout})"
