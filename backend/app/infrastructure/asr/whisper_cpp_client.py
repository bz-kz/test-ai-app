"""WhisperCppLocalASRClient: whisper-server HTTP API を介してローカル ASR を呼び出す実装。"""

from __future__ import annotations

import asyncio
import contextlib
import logging

import httpx

from .config import ASR_BASE_URL, ASR_MODEL, ASR_TIMEOUT_S
from .errors import ASRError
from .types import AudioPayload, TranscribeParams, TranscribeResponse, mask_phi

logger = logging.getLogger(__name__)

# ffmpeg コマンド引数: stdin から読み込み 16kHz モノラル 16-bit PCM WAV を stdout に出力する。
# -hide_banner / -loglevel error で余分な出力を抑制し、stderr にメタデータが漏れないようにする。
_FFMPEG_CMD = (
    "ffmpeg",
    "-hide_banner",
    "-loglevel",
    "error",
    "-i",
    "pipe:0",
    "-ac",
    "1",
    "-ar",
    "16000",
    "-c:a",
    "pcm_s16le",
    "-f",
    "wav",
    "pipe:1",
)


async def _transcode_to_wav(audio_bytes: bytes, source_mime: str) -> bytes:
    """音声バイト列を ffmpeg 経由で 16kHz モノラル 16-bit PCM WAV に変換する。

    stdin → stdout のパイプを使うためディスクには書き込まない。
    音声バイト列は PHI であるため、ファイルシステムへの永続化は禁止。
    タイムアウトは ASR_TIMEOUT_S の上限を用いる (トランスコード自体は数秒以内)。
    非ゼロ終了コード、または ffmpeg バイナリが存在しない場合は ASRError を送出する。

    source_mime が "audio/wav" で始まる場合は変換をスキップして直接返す。
    これにより WAV を渡すテストフィクスチャーがトランスコードを迂回できる。
    """
    # WAV ショートサーキット: 呼び出し元がすでに WAV バイト列を持っている場合は変換不要
    if source_mime.startswith("audio/wav"):
        return audio_bytes

    audio_len = len(audio_bytes)

    try:
        proc = await asyncio.create_subprocess_exec(
            *_FFMPEG_CMD,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            # stderr は PHI メタデータを含む可能性があるためキャプチャして破棄する
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        # ffmpeg バイナリが存在しない場合はオペレーターに再ビルドを促すログを出す
        logger.error(
            "ffmpeg binary not found; rebuild backend image with: apt-get install -y ffmpeg"
        )
        raise ASRError(
            "ffmpeg binary not found; backend image rebuild required",
            audio_length=audio_len,
        ) from exc

    try:
        stdout, _stderr = await asyncio.wait_for(
            proc.communicate(input=audio_bytes),
            timeout=ASR_TIMEOUT_S,
        )
    except TimeoutError as exc:
        # タイムアウト時はプロセスを強制終了してリソースを解放する
        with contextlib.suppress(ProcessLookupError):
            proc.kill()
        raise ASRError(
            "audio transcode timed out",
            audio_length=audio_len,
            timeout=True,
        ) from exc

    if proc.returncode != 0:
        # stderr の内容はメタデータ漏洩を防ぐためログに書かない
        raise ASRError(
            "audio transcode failed",
            audio_length=audio_len,
        )

    return stdout


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

        WebM/Opus などの非 WAV フォーマットは ffmpeg で 16kHz PCM WAV に変換してから送信する。
        audio.audio_bytes はトランスコード後に参照を解放する (GC に任せる)。
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

        # WAV 以外のフォーマットを whisper-server が受け付けるよう PCM WAV に変換する (BE-016)
        wav_bytes = await _transcode_to_wav(audio.audio_bytes, audio.content_type)
        # 元の音声バイト列への参照を解放し GC に回収させる
        del audio

        files = {
            # whisper-server は "file" フィールドで音声を受け取る
            "file": ("audio.wav", wav_bytes, "audio/wav"),
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

        # whisper-server は音声デコード失敗時も HTTP 200 で {"text": ""} を返す (BE-016)
        # 空テキストはデコード失敗と同義のため ASRError に変換して 503 を返す
        if not text:
            raise ASRError(
                "transcribe returned empty text (likely audio decode failure)",
                audio_length=audio_len,
                status_code=resp.status_code,
            )

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
