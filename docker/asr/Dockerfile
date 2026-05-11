# whisper.cpp サーバ — ネイティブ CPU 対応ビルド（arm64 / amd64 両対応）
#
# GHCR の ghcr.io/ggml-org/whisper.cpp:main は linux/amd64 のみ提供されており、
# Apple Silicon (arm64) で Rosetta 2 エミュレーション起動すると GGML 内部の
# CPU 機能検出ループで無限スピンが発生する（2026-05-12 確認）。
# そのためプラットフォームネイティブのバイナリをソースから cmake でビルドする。
# GPU は使用しない（CPU 推論のみ）— ADR-0001 参照。
#
# ビルドステージでコンパイルし、実行ステージにバイナリのみコピー。
# BUILD_SHARED_LIBS はデフォルト OFF のため静的リンクになり、共有ライブラリ不要。

# ---------- build stage ----------
FROM debian:bookworm-slim AS builder

ARG WHISPER_VERSION=v1.7.5

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        git \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src

# whisper.cpp をバージョンタグで取得（再現性のため）
RUN git clone --depth 1 --branch ${WHISPER_VERSION} \
        https://github.com/ggml-org/whisper.cpp.git .

# CPU のみビルド。WHISPER_BUILD_SERVER=ON でサーババイナリを生成。
# GGML_NATIVE=OFF: ホスト固有の SIMD 最適化を無効にし ARM vdotq_s32 コンパイルエラーを回避。
# docker buildx による aarch64 クロスビルドで arm_neon.h の dotprod ターゲットオプション
# ミスマッチが発生するため、ポータブルなビルドを優先する。
RUN cmake -S . -B build \
        -DCMAKE_BUILD_TYPE=Release \
        -DGGML_CUDA=OFF \
        -DGGML_METAL=OFF \
        -DGGML_NATIVE=OFF \
        -DWHISPER_BUILD_SERVER=ON \
    && cmake --build build --target whisper-server -j"$(nproc)"

# ---------- runtime stage ----------
FROM debian:bookworm-slim

# curl: モデルダウンロード用。python3: ヘルスチェック用。libgomp1: OpenMP ランタイム（libggml-cpu.so が要求）。
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        python3 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /src/build/bin/whisper-server /usr/local/bin/whisper-server

# whisper.cpp は shared libs でビルドされる — libwhisper.so と libggml*.so をコピー。
COPY --from=builder /src/build/src/libwhisper.so* /usr/local/lib/
COPY --from=builder /src/build/ggml/src/libggml-base.so /usr/local/lib/
COPY --from=builder /src/build/ggml/src/libggml-cpu.so /usr/local/lib/
COPY --from=builder /src/build/ggml/src/libggml.so /usr/local/lib/
RUN ldconfig

WORKDIR /app

EXPOSE 8080

# モデルダウンロードとサーバ起動を CMD で行う。
# /models は外部ボリュームとしてマウントされる (asr_data)。
# --no-gpu: CPU 推論強制（コンテナ内に GPU なし）。
ENTRYPOINT ["/bin/sh", "-c"]
CMD ["test -f /models/ggml-medium-q5_0.bin || curl -fsSL -o /models/ggml-medium-q5_0.bin https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium-q5_0.bin && exec whisper-server --host 0.0.0.0 --port 8080 -m /models/ggml-medium-q5_0.bin -l ja --no-gpu"]
