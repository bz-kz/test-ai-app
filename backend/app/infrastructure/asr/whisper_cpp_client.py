"""WhisperCppLocalASRClient: whisper-server HTTP API を介してローカル ASR を呼び出す実装。"""

from __future__ import annotations

import asyncio
import contextlib
import io
import logging
import time
import wave
from collections.abc import AsyncIterator

import httpx

from .config import ASR_BASE_URL, ASR_MODEL, ASR_STREAM_CHUNK_SECONDS, ASR_TIMEOUT_S
from .errors import ASRError
from .types import AudioPayload, TranscribeChunk, TranscribeParams, TranscribeResponse, mask_phi

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


def _slice_wav_to_chunks(wav_bytes: bytes, chunk_seconds: int) -> list[bytes]:
    """WAV バイト列をチャンク秒数でサンプル境界に揃えて分割し、各チャンクの完全 WAV を返す。

    Python 標準ライブラリの wave モジュールのみを使用する。新たな重い依存はない。
    各チャンクは 44 バイトの WAV ヘッダー + PCM_S16LE @ 16kHz モノラルのバイト列。
    最後のチャンクは chunk_seconds より短くなることがある。
    音声が chunk_seconds より短い場合は元の WAV を 1 チャンクとして返す。

    非 WAV ヘッダー・非 16kHz・非モノラル・非 PCM_S16LE の場合は ASRError を送出する。
    """
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as src:
            n_channels = src.getnchannels()
            sampwidth = src.getsampwidth()
            framerate = src.getframerate()
            n_frames = src.getnframes()
            # 全フレームを一括読み込み (in-memory なのでディスクに書かない)
            pcm_data = src.readframes(n_frames)
    except (wave.Error, EOFError, OSError) as exc:
        raise ASRError(
            f"failed to read WAV header: {type(exc).__name__}",
            audio_length=len(wav_bytes),
        ) from exc

    # フォーマット検証: whisper-server は 16kHz モノラル PCM_S16LE のみサポート
    if n_channels != 1:
        raise ASRError(
            f"WAV must be mono (got {n_channels} channels)",
            audio_length=len(wav_bytes),
        )
    if framerate != 16000:
        raise ASRError(
            f"WAV must be 16kHz (got {framerate}Hz)",
            audio_length=len(wav_bytes),
        )
    if sampwidth != 2:
        # 2 バイト = 16-bit = PCM_S16LE
        raise ASRError(
            f"WAV must be PCM_S16LE / 16-bit (got sampwidth={sampwidth})",
            audio_length=len(wav_bytes),
        )

    # フレーム数をチャンク秒数で分割する
    frames_per_chunk = framerate * chunk_seconds
    bytes_per_frame = n_channels * sampwidth

    chunks: list[bytes] = []
    offset = 0
    while offset < len(pcm_data):
        slice_bytes = pcm_data[offset : offset + frames_per_chunk * bytes_per_frame]
        offset += frames_per_chunk * bytes_per_frame

        # 各チャンク用の完全 WAV をインメモリで構築する
        buf = io.BytesIO()
        with wave.open(buf, "wb") as dst:
            dst.setnchannels(n_channels)
            dst.setsampwidth(sampwidth)
            dst.setframerate(framerate)
            dst.writeframes(slice_bytes)
        chunks.append(buf.getvalue())

    # 音声が chunk_seconds 未満の場合は元の WAV をそのまま 1 チャンクとして返す
    if not chunks:
        chunks.append(wav_bytes)

    return chunks


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
        stream_chunk_seconds: int = ASR_STREAM_CHUNK_SECONDS,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_s = timeout_s
        self._stream_chunk_seconds = stream_chunk_seconds

    async def _post_chunk_to_whisper(
        self,
        chunk_wav: bytes,
        params: TranscribeParams,
        chunk_index: int,
        audio_len: int,
    ) -> str:
        """単一チャンク WAV を whisper-server /inference に POST してテキストを返す。

        空テキスト・非200・タイムアウト時は ASRError を送出する。
        """
        files = {"file": ("audio.wav", chunk_wav, "audio/wav")}
        data = {"language": params.language, "response_format": "json"}

        try:
            async with httpx.AsyncClient(timeout=self._timeout_s) as client:
                resp = await client.post(
                    f"{self._base_url}/inference",
                    files=files,
                    data=data,
                )
        except httpx.TimeoutException as exc:
            raise ASRError(
                f"chunk {chunk_index} transcribe timed out",
                audio_length=audio_len,
                timeout=True,
            ) from exc
        except httpx.HTTPError as exc:
            raise ASRError(
                f"chunk {chunk_index} HTTP error: {type(exc).__name__}",
                audio_length=audio_len,
            ) from exc

        if resp.status_code != 200:
            raise ASRError(
                f"chunk {chunk_index} returned non-200: {resp.status_code}",
                audio_length=audio_len,
                status_code=resp.status_code,
            )

        body = resp.json()
        text: str = body.get("text", "").strip()

        # whisper-server は音声デコード失敗時も HTTP 200 で {"text": ""} を返す (BE-016)
        if not text:
            raise ASRError(
                f"transcribe returned empty text (chunk {chunk_index})",
                audio_length=audio_len,
                status_code=resp.status_code,
            )

        return text

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

    def stream_transcribe(
        self,
        audio: AudioPayload,
        params: TranscribeParams | None = None,
    ) -> AsyncIterator[TranscribeChunk]:
        """音声をチャンク分割して逐次文字起こしし TranscribeChunk を yield する (BE-017)。

        処理順序:
          1. _transcode_to_wav で 16kHz PCM WAV に変換する (BE-016 を再利用)。
          2. _slice_wav_to_chunks で chunk_seconds 単位に分割する。
          3. 各チャンクを whisper-server /inference に逐次 POST して TranscribeChunk を yield する。
          4. 全チャンク完了後に done=True の完了チャンクを yield する。

        mid-stream エラーは ASRError として伝播する (呼び出し元がイテレータを停止する)。
        音声バイト列・PCM スライス・チャンクテキストはログに書かない (PHI)。
        同期メソッドとして async generator を返す (Protocol 規約に準拠)。
        """
        return self._stream_transcribe_impl(audio, params)

    async def _stream_transcribe_impl(
        self,
        audio: AudioPayload,
        params: TranscribeParams | None = None,
    ) -> AsyncIterator[TranscribeChunk]:
        """stream_transcribe の実体 (async generator)。

        同期の stream_transcribe から呼び出されることで、
        async generator として動作する。
        """
        p = params or TranscribeParams()
        audio_len = len(audio.audio_bytes)

        logger.debug(
            "stream_transcribe request: model=%s audio_length=%s chunk_seconds=%d",
            self._model,
            mask_phi(str(audio_len)),
            self._stream_chunk_seconds,
        )

        # (1) 16kHz PCM WAV にトランスコード (BE-016 再利用)
        wav_bytes = await _transcode_to_wav(audio.audio_bytes, audio.content_type)
        del audio  # 元の音声バイト列への参照を解放

        # (2) chunk_seconds 単位に WAV を分割
        chunks = _slice_wav_to_chunks(wav_bytes, self._stream_chunk_seconds)
        del wav_bytes  # WAV 全体への参照を解放
        n = len(chunks)

        logger.info(
            "stream_transcribe: model=%s chunk_count=%d",
            self._model,
            n,
        )

        # (3) 各チャンクを逐次 POST して yield する
        assembled_parts: list[str] = []
        start_time = time.monotonic()

        for i, chunk_wav in enumerate(chunks):
            text = await self._post_chunk_to_whisper(chunk_wav, p, i, audio_len)
            assembled_parts.append(text)
            # チャンクテキストはログに書かない; 長さのみ記録する
            logger.debug(
                "stream_transcribe chunk %d/%d: text_length=%d",
                i,
                n,
                len(text),
            )
            yield TranscribeChunk(
                text=text,
                chunk_index=i,
                chunk_count=n,
                done=False,
            )

        # (4) 完了チャンクを yield する
        elapsed = time.monotonic() - start_time
        full_text = "".join(assembled_parts)
        logger.info(
            "stream_transcribe done: model=%s chunk_count=%d duration_s=%.1f",
            self._model,
            n,
            elapsed,
        )
        yield TranscribeChunk(
            text=full_text,
            chunk_index=n - 1,
            chunk_count=n,
            done=True,
        )

    async def ping(self) -> bool:
        """whisper-server の / に GET して到達可能性を確認する。例外を送出しない。"""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self._base_url}/")
                return resp.status_code == 200
        except Exception:
            logger.warning("ASR ping failed (host=%s)", self._base_url)
            return False
