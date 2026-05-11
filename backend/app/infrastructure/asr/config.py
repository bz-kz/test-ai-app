"""ASR インフラ層の設定値。環境変数から読み込む。ハードコード禁止。"""

from __future__ import annotations

import os

# デフォルト値はドキュメント目的; 必ず環境変数で上書きすること
ASR_BASE_URL: str = os.getenv("ASR_BASE_URL", "http://asr:8080")

# ADR-0001 で固定されたモデルファイル名。変更には ADR が必要。
ASR_MODEL: str = os.getenv("ASR_MODEL", "ggml-medium-q5_0.bin")

# transcribe() のタイムアウト秒数。RTF ≤1.5× の 60s クリップをカバーする (≤90s)。
ASR_TIMEOUT_S: float = float(os.getenv("ASR_TIMEOUT_S", "90"))
