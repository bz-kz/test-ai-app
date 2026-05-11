"""LLM ライブ統合テスト。実 Ollama コンテナが必要。デフォルト pytest -q では除外される。

実行方法: pytest -m integration -v
"""

from __future__ import annotations

import pytest

from app.infrastructure.llm import OllamaLocalLLMClient


@pytest.mark.integration
async def test_live_ping() -> None:
    """実 Ollama に ping して True が返ることを確認する。"""
    client = OllamaLocalLLMClient()
    result = await client.ping()
    assert result is True


@pytest.mark.integration
async def test_live_generate() -> None:
    """実 Ollama に最小限のプロンプトを送って応答テキストが返ることを確認する。

    PHI は含まない ASCII 文字列のみ使用する。
    """
    client = OllamaLocalLLMClient()
    result = await client.generate("ping")
    assert isinstance(result.text, str)
    assert len(result.text) > 0
