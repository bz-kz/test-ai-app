# マルチステージビルド — standalone 出力でイメージサイズを削減
FROM node:22-alpine AS base

FROM base AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# NEXT_PUBLIC_* は build 時に JS バンドルへ焼かれる (Next.js の仕様)。
# docker-compose.yml の frontend.build.args 経由で値を受け取る。
# 未指定時のデフォルトは frontend/src/lib/constants.ts で吸収する (ASR_STREAMING_ENABLED=false)。
ARG NEXT_PUBLIC_API_BASE_URL
ARG NEXT_PUBLIC_ASR_STREAMING_ENABLED
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
ENV NEXT_PUBLIC_ASR_STREAMING_ENABLED=$NEXT_PUBLIC_ASR_STREAMING_ENABLED
RUN npm run build

FROM base AS runner
WORKDIR /app

ENV NODE_ENV=production

RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# public ディレクトリは存在しない場合があるため mkdir で保証してからコピー
RUN mkdir -p ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]
