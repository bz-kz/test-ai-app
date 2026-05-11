FROM python:3.12-slim

WORKDIR /app

# 依存パッケージを先にインストールしてレイヤーキャッシュを活かす
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
