"""FakeLocalASRClient: ユニットテスト用の決定論的 ASR スタブ。

本番コードには絶対にインポートしないこと。tests/ と conftest.py のみで使う。
"""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import AsyncIterator

from .errors import ASRError
from .types import AudioPayload, TranscribeChunk, TranscribeParams, TranscribeResponse

# デフォルトの固定応答テキスト (合成日本語)
DEFAULT_TRANSCRIPT: str = "患者は頭痛と発熱を訴えています。"


class FakeLocalASRClient:
    """決定論的なトランスクリプトを返すテスト用スタブ。

    fixture_map で sha256(audio_bytes)[:16] → トランスクリプトを登録できる。
    登録されていない音声は DEFAULT_TRANSCRIPT を返す。
    force_error=True にすると次の呼び出しで ASRError を送出する。
    force_timeout=True にすると timeout=True の ASRError を送出する。

    stream_transcribe は DEFAULT_TRANSCRIPT を n_chunks (デフォルト 3) に等分割して yield する。
    per_chunk_delay_s で各チャンク間の遅延を設定できる (レイテンシ層テスト用)。
    force_error_at_chunk でチャンク N で ASRError を送出させられる。
    force_total_timeout=True で asyncio.TimeoutError を擬似するため
    timeout=True の ASRError を送出する。
    """

    DEFAULT_TRANSCRIPT: str = DEFAULT_TRANSCRIPT

    def __init__(
        self,
        fixture_map: dict[str, str] | None = None,
        *,
        force_error: bool = False,
        force_timeout: bool = False,
        ping_result: bool = True,
        # stream_transcribe 専用オプション
        n_chunks: int = 3,
        per_chunk_delay_s: float = 0.0,
        force_error_at_chunk: int | None = None,
        force_total_timeout: bool = False,
    ) -> None:
        # キー: sha256(audio_bytes)[:16]
        self._fixture_map: dict[str, str] = fixture_map or {}
        self._force_error = force_error
        self._force_timeout = force_timeout
        self._ping_result = ping_result
        self._n_chunks = max(1, n_chunks)
        self._per_chunk_delay_s = per_chunk_delay_s
        self._force_error_at_chunk = force_error_at_chunk
        self._force_total_timeout = force_total_timeout
        # 呼び出し回数を記録しテストアサーションに使えるようにする
        self.transcribe_call_count: int = 0
        self.stream_transcribe_call_count: int = 0
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

    def stream_transcribe(
        self,
        audio: AudioPayload,
        params: TranscribeParams | None = None,
    ) -> AsyncIterator[TranscribeChunk]:
        """決定論的なチャンク列を yield するストリーム用スタブ。

        DEFAULT_TRANSCRIPT を n_chunks に等分割してチャンクとして yield する。
        per_chunk_delay_s > 0 の場合は各チャンク後に asyncio.sleep で遅延する。
        force_error_at_chunk=N の場合、チャンク N で ASRError を送出してイテレータを停止する。
        force_total_timeout=True の場合、最初のチャンクで timeout=True の ASRError を送出する。
        同期メソッドとして async generator を返す (Protocol 規約に準拠)。
        """
        return self._stream_impl(audio, params)

    async def _stream_impl(
        self,
        audio: AudioPayload,
        params: TranscribeParams | None = None,
    ) -> AsyncIterator[TranscribeChunk]:
        """stream_transcribe の実体 (async generator)。"""
        self.stream_transcribe_call_count += 1
        audio_len = len(audio.audio_bytes)

        # force_total_timeout は最初のチャンクで timeout=True の ASRError を送出する
        if self._force_total_timeout:
            raise ASRError(
                "forced total timeout in FakeLocalASRClient",
                audio_length=audio_len,
                timeout=True,
            )

        # fixture_map のキーは sha256(bytes)[:16] で探す
        key = hashlib.sha256(audio.audio_bytes).hexdigest()[:16]
        full_text = self._fixture_map.get(key, self.DEFAULT_TRANSCRIPT)

        n = self._n_chunks
        # テキストを n 等分割する (最後のチャンクに余りが入る)
        chunk_size = max(1, len(full_text) // n)
        text_chunks: list[str] = []
        for i in range(n):
            start = i * chunk_size
            end = start + chunk_size if i < n - 1 else len(full_text)
            text_chunks.append(full_text[start:end])

        assembled: list[str] = []
        for i, chunk_text in enumerate(text_chunks):
            # force_error_at_chunk: 指定チャンクで ASRError を送出する
            if self._force_error_at_chunk is not None and i == self._force_error_at_chunk:
                raise ASRError(
                    f"forced error at chunk {i} in FakeLocalASRClient",
                    audio_length=audio_len,
                )

            assembled.append(chunk_text)

            if self._per_chunk_delay_s > 0:
                await asyncio.sleep(self._per_chunk_delay_s)

            yield TranscribeChunk(
                text=chunk_text,
                chunk_index=i,
                chunk_count=n,
                done=False,
            )

        # 完了チャンク
        yield TranscribeChunk(
            text="".join(assembled),
            chunk_index=n - 1,
            chunk_count=n,
            done=True,
        )

    async def ping(self) -> bool:
        self.ping_call_count += 1
        return self._ping_result
