"""OllamaLocalLLMClient: Ollama 互換 API を介してローカル LLM を呼び出す実装。"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import AsyncIterator

import httpx

from .config import LLM_BASE_URL, LLM_MODEL, LLM_TIMEOUT_S
from .errors import InferenceError
from .types import Chunk, GenerateParams, GenerateResponse, mask_phi

logger = logging.getLogger(__name__)


class OllamaLocalLLMClient:
    """Ollama API（/api/generate, /api/tags）を介してローカル Gemma を呼び出す。

    PHI 規則: プロンプトや応答をログに書く際は必ず mask_phi() を通す。
    """

    def __init__(
        self,
        base_url: str = LLM_BASE_URL,
        model: str = LLM_MODEL,
        timeout_s: float = LLM_TIMEOUT_S,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_s = timeout_s

    async def generate(
        self,
        prompt: str,
        params: GenerateParams | None = None,
    ) -> GenerateResponse:
        """Ollama /api/generate に POST してレスポンス全体を返す。"""
        p = params or GenerateParams()
        payload: dict[str, object] = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": p.temperature,
                "num_predict": p.max_tokens,
                **p.extra,
            },
        }
        # プロンプトはログに出さない; マスク済みプレビューのみ記録する
        logger.debug("generate request: model=%s prompt=%s", self._model, mask_phi(prompt))

        start_time = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=self._timeout_s) as client:
                resp = await client.post(f"{self._base_url}/api/generate", json=payload)
        except httpx.TimeoutException as exc:
            elapsed = time.monotonic() - start_time
            logger.info(
                "generate timeout: model=%s prompt_length=%d elapsed_s=%.2f",
                self._model,
                len(prompt),
                elapsed,
            )
            raise InferenceError(
                "generate timed out",
                raw_prompt=prompt,
                status_code=None,
            ) from exc
        except httpx.HTTPError as exc:
            elapsed = time.monotonic() - start_time
            logger.info(
                "generate http_error: model=%s prompt_length=%d elapsed_s=%.2f kind=%s",
                self._model,
                len(prompt),
                elapsed,
                type(exc).__name__,
            )
            raise InferenceError(
                f"generate HTTP error: {type(exc).__name__}",
                raw_prompt=prompt,
                status_code=None,
            ) from exc

        if resp.status_code != 200:
            elapsed = time.monotonic() - start_time
            logger.info(
                "generate non_200: model=%s prompt_length=%d elapsed_s=%.2f status=%d",
                self._model,
                len(prompt),
                elapsed,
                resp.status_code,
            )
            raise InferenceError(
                f"generate returned non-200: {resp.status_code}",
                raw_prompt=prompt,
                status_code=resp.status_code,
            )

        data = resp.json()
        text: str = data.get("response", "")
        elapsed = time.monotonic() - start_time
        # PHI 規則: INFO ログには長さと経過時間のみ。プロンプト/応答本文は debug のみ。
        logger.info(
            "generate done: model=%s prompt_length=%d text_length=%d total_elapsed_s=%.2f",
            self._model,
            len(prompt),
            len(text),
            elapsed,
        )
        logger.debug("generate response: model=%s text=%s", self._model, mask_phi(text))
        return GenerateResponse(text=text)

    async def stream(
        self,
        prompt: str,
        params: GenerateParams | None = None,
    ) -> AsyncIterator[Chunk]:
        """Ollama /api/generate（stream=true）からチャンクを非同期イテレータで返す。

        エンドツーエンドタイムアウトは timeout_s × 2 を上限とする。
        """
        p = params or GenerateParams()
        payload: dict[str, object] = {
            "model": self._model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": p.temperature,
                "num_predict": p.max_tokens,
                **p.extra,
            },
        }
        logger.debug("stream request: model=%s prompt=%s", self._model, mask_phi(prompt))

        start_time = time.monotonic()
        ttft_s: float | None = None
        chunk_count = 0
        total_text_length = 0
        try:
            async with (
                httpx.AsyncClient(timeout=self._timeout_s * 2) as client,
                client.stream("POST", f"{self._base_url}/api/generate", json=payload) as resp,
            ):
                if resp.status_code != 200:
                    elapsed = time.monotonic() - start_time
                    logger.info(
                        "stream non_200: model=%s prompt_length=%d elapsed_s=%.2f status=%d",
                        self._model,
                        len(prompt),
                        elapsed,
                        resp.status_code,
                    )
                    raise InferenceError(
                        f"stream returned non-200: {resp.status_code}",
                        raw_prompt=prompt,
                        status_code=resp.status_code,
                    )
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    text: str = data.get("response", "")
                    done: bool = data.get("done", False)
                    # 最初の非空チャンク到着時に TTFT を確定する
                    if ttft_s is None and text:
                        ttft_s = time.monotonic() - start_time
                    chunk_count += 1
                    total_text_length += len(text)
                    yield Chunk(text=text, done=done)
                    if done:
                        break
        except httpx.TimeoutException as exc:
            elapsed = time.monotonic() - start_time
            logger.info(
                "stream timeout: model=%s prompt_length=%d elapsed_s=%.2f chunks=%d",
                self._model,
                len(prompt),
                elapsed,
                chunk_count,
            )
            raise InferenceError(
                "stream timed out",
                raw_prompt=prompt,
                status_code=None,
            ) from exc
        except httpx.HTTPError as exc:
            elapsed = time.monotonic() - start_time
            logger.info(
                "stream http_error: model=%s prompt_length=%d elapsed_s=%.2f chunks=%d kind=%s",
                self._model,
                len(prompt),
                elapsed,
                chunk_count,
                type(exc).__name__,
            )
            raise InferenceError(
                f"stream HTTP error: {type(exc).__name__}",
                raw_prompt=prompt,
                status_code=None,
            ) from exc

        total_elapsed = time.monotonic() - start_time
        # ttft_s が None の場合は応答が空で終了したことを示す (-1 をセンチネルに使用)
        logger.info(
            "stream done: model=%s prompt_length=%d chunks=%d text_length=%d "
            "ttft_s=%.2f total_elapsed_s=%.2f",
            self._model,
            len(prompt),
            chunk_count,
            total_text_length,
            ttft_s if ttft_s is not None else -1.0,
            total_elapsed,
        )

    async def ping(self) -> bool:
        """Ollama /api/tags に GET して到達可能性を確認する。例外を送出しない。"""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self._base_url}/api/tags")
                return resp.status_code == 200
        except Exception:
            logger.warning("LLM ping failed (host=%s)", self._base_url)
            return False
