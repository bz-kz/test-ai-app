"""FakeLocalLLMClient: ユニットテスト用の決定論的 LLM スタブ。

本番コードには絶対にインポートしないこと。tests/ と conftest.py のみで使う。
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from .errors import InferenceError
from .types import Chunk, GenerateParams, GenerateResponse

# デフォルトのフィクスチャマップ: プロンプトキー → 応答テキスト
DEFAULT_FIXTURE_MAP: dict[str, str] = {
    "ping": "pong",
    "hello": "こんにちは",
}


class FakeLocalLLMClient:
    """決定論的な応答を返すテスト用スタブ。

    fixture_map で任意のプロンプト → 応答を登録できる。
    登録されていないプロンプトは DEFAULT_RESPONSE を返す。
    force_error=True にすると次の呼び出しで InferenceError を送出する。
    """

    DEFAULT_RESPONSE: str = "[fake response]"

    def __init__(
        self,
        fixture_map: dict[str, str] | None = None,
        *,
        force_error: bool = False,
        ping_result: bool = True,
    ) -> None:
        self._fixture_map: dict[str, str] = fixture_map or dict(DEFAULT_FIXTURE_MAP)
        self._force_error = force_error
        self._ping_result = ping_result
        # 呼び出し回数を記録しテストアサーションに使えるようにする
        self.generate_call_count: int = 0
        self.stream_call_count: int = 0
        self.ping_call_count: int = 0

    async def generate(
        self,
        prompt: str,
        params: GenerateParams | None = None,
    ) -> GenerateResponse:
        self.generate_call_count += 1
        if self._force_error:
            raise InferenceError("forced error in FakeLocalLLMClient", raw_prompt=prompt)
        text = self._fixture_map.get(prompt, self.DEFAULT_RESPONSE)
        return GenerateResponse(text=text)

    async def stream(
        self,
        prompt: str,
        params: GenerateParams | None = None,
    ) -> AsyncIterator[Chunk]:
        """フィクスチャテキストを単一チャンクとして返す非同期イテレータ。"""
        return self._stream_impl(prompt, params)

    async def _stream_impl(
        self,
        prompt: str,
        params: GenerateParams | None = None,
    ) -> AsyncIterator[Chunk]:
        self.stream_call_count += 1
        if self._force_error:
            raise InferenceError("forced error in FakeLocalLLMClient", raw_prompt=prompt)
        text = self._fixture_map.get(prompt, self.DEFAULT_RESPONSE)
        yield Chunk(text=text, done=False)
        yield Chunk(text="", done=True)

    async def ping(self) -> bool:
        self.ping_call_count += 1
        return self._ping_result
