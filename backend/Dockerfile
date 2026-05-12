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

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
