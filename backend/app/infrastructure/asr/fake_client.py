"""FakeLocalASRClient: ユニットテスト用の決定論的 ASR スタブ。

本番コードには絶対にインポートしないこと。tests/ と conftest.py のみで使う。
"""

from __future__ import annotations

import hashlib

from .errors import ASRError
from .types import AudioPayload, TranscribeParams, TranscribeResponse

# デフォルトの固定応答テキスト (合成日本語)
DEFAULT_TRANSCRIPT: str = "患者は頭痛と発熱を訴えています。"


class FakeLocalASRClient:
    """決定論的なトランスクリプトを返すテスト用スタブ。

    fixture_map で sha256(audio_bytes)[:16] → トランスクリプトを登録できる。
    登録されていない音声は DEFAULT_TRANSCRIPT を返す。
    force_error=True にすると次の呼び出しで ASRError を送出する。
    force_timeout=True にすると timeout=True の ASRError を送出する。
    """

    DEFAULT_TRANSCRIPT: str = DEFAULT_TRANSCRIPT

    def __init__(
        self,
        fixture_map: dict[str, str] | None = None,
        *,
        force_error: bool = False,
        force_timeout: bool = False,
        ping_result: bool = True,
    ) -> None:
        # キー: sha256(audio_bytes)[:16]
        self._fixture_map: dict[str, str] = fixture_map or {}
        self._force_error = force_error
        self._force_timeout = force_timeout
        self._ping_result = ping_result
        # 呼び出し回数を記録しテストアサーションに使えるようにする
        self.transcribe_call_count: int = 0
        self.ping_call_count: int = 0

    async def transcribe(
        self,
        audio: AudioPayload,
        params: TranscribeParams | None = None,
    ) -> TranscribeResponse:
        self.transcribe_call_count += 1
        if self._force_error:
            raise ASRError(
                "forced error in FakeLocalASRClient",
                audio_length=len(audio.audio_bytes),
            )
        if self._force_timeout:
            raise ASRError(
                "forced timeout in FakeLocalASRClient",
                audio_length=len(audio.audio_bytes),
                timeout=True,
            )
        # fixture_map のキーは sha256(bytes)[:16] で探す
        key = hashlib.sha256(audio.audio_bytes).hexdigest()[:16]
        text = self._fixture_map.get(key, self.DEFAULT_TRANSCRIPT)
        return TranscribeResponse(text=text)

    async def ping(self) -> bool:
        self.ping_call_count += 1
        return self._ping_result
