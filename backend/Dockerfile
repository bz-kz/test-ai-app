FROM python:3.12-slim

WORKDIR /app

# ffmpeg は WebM/Opus → PCM WAV 変換に必要 (BE-016)
# whisper.cpp ソースビルドは ffmpeg なしのため backend 側でトランスコードする
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

# 依存パッケージを先にインストールしてレイヤーキャッシュを活かす
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# ADR-0006: OTel auto-instrumentation を起動ラッパ経由で有効化。
# `opentelemetry-instrument` は OTEL_* env vars (compose lines 152-169) を読んで
# FastAPI/httpx/sqlalchemy/asyncpg/logging の各 instrumentation を起動時に注入する。
CMD ["opentelemetry-instrument", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
