"""推論層の例外定義。プロンプト原文は __str__ / __repr__ に含まない。"""

from __future__ import annotations

from .types import mask_phi


class InferenceError(Exception):
    """LLM 呼び出しの失敗を表す型付き例外。

    raw_prompt は保持するが __str__ / __repr__ には出力しない。
    ログに渡す際は必ず masked_context を使うこと。
    """

    def __init__(
        self,
        message: str,
        *,
        raw_prompt: str | None = None,
        status_code: int | None = None,
    ) -> None:
        # プロンプト原文は内部属性として保持するが外部に露出しない
        self._raw_prompt = raw_prompt
        self.status_code = status_code
        # マスク済みコンテキストをメッセージに付与する
        masked = mask_phi(raw_prompt) if raw_prompt else "<no prompt>"
        self.masked_context = f"{message} | context: {masked}"
        # 親クラスには安全なメッセージのみ渡す
        super().__init__(self.masked_context)

    def __str__(self) -> str:
        # raw_prompt を含まない安全な表現を返す
        return self.masked_context

    def __repr__(self) -> str:
        # raw_prompt を含まない安全な表現を返す
        status = f", status_code={self.status_code}" if self.status_code is not None else ""
        return f"InferenceError({self.masked_context!r}{status})"
