"""LLM インフラ層の設定値。環境変数から読み込む。ハードコード禁止。"""

from __future__ import annotations

import os

# デフォルト値はドキュメント目的; 必ず環境変数で上書きすること
LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "http://llm:11434")

# Spec で固定されたモデル名。変更には ADR が必要。
LLM_MODEL: str = os.getenv("LLM_MODEL", "gemma4:e4b")

# generate() のタイムアウト秒数。stream() は 2 倍を上限とする。
LLM_TIMEOUT_S: float = float(os.getenv("LLM_TIMEOUT_S", "60"))
