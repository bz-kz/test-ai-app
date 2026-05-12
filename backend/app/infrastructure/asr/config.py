"""ASR インフラ層の設定値。環境変数から読み込む。ハードコード禁止。"""

from __future__ import annotations

import os

# デフォルト値はドキュメント目的; 必ず環境変数で上書きすること
ASR_BASE_URL: str = os.getenv("ASR_BASE_URL", "http://asr:8080")

# ADR-0001 で固定されたモデルファイル名。変更には ADR が必要。
ASR_MODEL: str = os.getenv("ASR_MODEL", "ggml-medium-q5_0.bin")

# transcribe() のタイムアウト秒数。RTF ≤1.5× の 60s クリップをカバーする (≤90s)。
ASR_TIMEOUT_S: float = float(os.getenv("ASR_TIMEOUT_S", "90"))

# --- ストリーミング設定 (BE-017 / ADR-0003) ---

# チャンクサイズ (秒)。[5, 20] の範囲外はモジュールインポート時にエラーを送出する。
_raw_chunk_seconds = int(os.getenv("ASR_STREAM_CHUNK_SECONDS", "10"))
if not (5 <= _raw_chunk_seconds <= 20):
    raise ValueError(
        f"ASR_STREAM_CHUNK_SECONDS must be in the inclusive range [5, 20], got {_raw_chunk_seconds}"
    )
ASR_STREAM_CHUNK_SECONDS: int = _raw_chunk_seconds

# ストリーム全体のエンドツーエンドタイムアウト (秒)。asyncio.wait_for で強制する。
ASR_STREAM_TOTAL_TIMEOUT_S: int = int(os.getenv("ASR_STREAM_TOTAL_TIMEOUT_S", "180"))

# 初回チャンクのレイテンシ目標 (秒)。ソフトターゲット — ハードタイムアウトではない。
# cost-check がこの値を参照して p95 ≤ 25s を検証する。
ASR_STREAM_FIRST_CHUNK_LATENCY_S: int = int(os.getenv("ASR_STREAM_FIRST_CHUNK_LATENCY_S", "25"))
