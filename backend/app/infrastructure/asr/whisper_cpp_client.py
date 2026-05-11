"""WhisperCppLocalASRClient: whisper-server HTTP API を介してローカル ASR を呼び出す実装。"""

from __future__ import annotations

import logging

import httpx

from .config import ASR_BASE_URL, ASR_MODEL, ASR_TIMEOUT_S
from .errors import ASRError
from .types import AudioPayload, TranscribeParams, TranscribeResponse, mask_phi

logger = logging.getLogger(__name__)


class WhisperCppLocalASRClient:
    """whisper-server の /inference エンドポイントを multipart form-data で呼び出す。

    PHI 規則:
      - 音声バイト列・ファイル名・トランスクリプトはログに書かない。
      - ログに書く場合は必ず mask_phi() を通す。
      - ASRError の context には音声長のみ含める。
    """

    def __init__(
        self,
        base_url: str = ASR_BASE_URL,
        model: str = ASR_MODEL,
        timeout_s: float = ASR_TIMEOUT_S,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_s = timeout_s

    async def transcribe(
        self,
        audio: AudioPayload,
        params: TranscribeParams | None = None,
    ) -> TranscribeResponse:
        """whisper-server POST /inference に multipart で送信して文字起こし結果を返す。

        音声バイト列はリクエスト後すぐに解放される (呼び出し元の SpooledTemporaryFile も同様)。
        トランスクリプト本文はログに書かない。長さのみ DEBUG で記録する。
        """
        p = params or TranscribeParams()
        audio_len = len(audio.audio_bytes)
        # 音声データはログに書かない; 長さのみ記録する
        logger.debug(
            "transcribe request: model=%s audio_length=%s",
            self._model,
            mask_phi(str(audio_len)),
        )

        files = {
            # whisper-server は "file" フィールドで音声を受け取る
            "file": ("audio", audio.audio_bytes, audio.content_type),
        }
        data = {
            "language": p.language,
            "response_format": "json",
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout_s) as client:
                resp = await client.post(
                    f"{self._base_url}/inference",
                    files=files,
                    data=data,
                )
        except httpx.TimeoutException as exc:
            raise ASRError(
                "transcribe timed out",
                audio_length=audio_len,
                timeout=True,
            ) from exc
        except httpx.HTTPError as exc:
            raise ASRError(
                f"transcribe HTTP error: {type(exc).__name__}",
                audio_length=audio_len,
            ) from exc

        if resp.status_code != 200:
            raise ASRError(
                f"transcribe returned non-200: {resp.status_code}",
                audio_length=audio_len,
                status_code=resp.status_code,
            )

        body = resp.json()
        text: str = body.get("text", "").strip()
        # duration_ms → duration_seconds 変換 (whisper-server がミリ秒で返す場合あり)
        duration_ms: float | None = body.get("duration") or body.get("duration_ms")
        duration_seconds: float | None = (duration_ms / 1000.0) if duration_ms is not None else None

        # トランスクリプト本文はログに書かない; 長さのみ記録する
        logger.debug(
            "transcribe response: model=%s text_length=%d duration_s=%s",
            self._model,
            len(text),
            duration_seconds,
        )
        return TranscribeResponse(text=text, duration_seconds=duration_seconds)

    async def ping(self) -> bool:
        """whisper-server の / に GET して到達可能性を確認する。例外を送出しない。"""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self._base_url}/")
                return resp.status_code == 200
        except Exception:
            logger.warning("ASR ping failed (host=%s)", self._base_url)
            return False
