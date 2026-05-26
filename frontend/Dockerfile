# マルチステージビルド — standalone 出力でイメージサイズを削減
FROM node:22-alpine AS base
# corepack 経由で package.json の packageManager 指定 (pnpm) を有効化
RUN corepack enable

FROM base AS deps
WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

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
# ADR-0006 FE-015: Datadog Browser RUM の env を build-time bake。
# applicationId / clientToken が未設定なら lib/datadog-rum.ts 側で init を no-op にする。
ARG NEXT_PUBLIC_RUM_ENABLED
ARG NEXT_PUBLIC_DD_RUM_APPLICATION_ID
ARG NEXT_PUBLIC_DD_RUM_CLIENT_TOKEN
ARG NEXT_PUBLIC_DD_SITE
ARG NEXT_PUBLIC_DD_RUM_SERVICE
ARG NEXT_PUBLIC_DD_RUM_ENV
ARG NEXT_PUBLIC_DD_RUM_VERSION
ENV NEXT_PUBLIC_RUM_ENABLED=$NEXT_PUBLIC_RUM_ENABLED
ENV NEXT_PUBLIC_DD_RUM_APPLICATION_ID=$NEXT_PUBLIC_DD_RUM_APPLICATION_ID
ENV NEXT_PUBLIC_DD_RUM_CLIENT_TOKEN=$NEXT_PUBLIC_DD_RUM_CLIENT_TOKEN
ENV NEXT_PUBLIC_DD_SITE=$NEXT_PUBLIC_DD_SITE
ENV NEXT_PUBLIC_DD_RUM_SERVICE=$NEXT_PUBLIC_DD_RUM_SERVICE
ENV NEXT_PUBLIC_DD_RUM_ENV=$NEXT_PUBLIC_DD_RUM_ENV
ENV NEXT_PUBLIC_DD_RUM_VERSION=$NEXT_PUBLIC_DD_RUM_VERSION
# pnpm 11 の runDepsStatusCheck が TTY 待ちで abort するのを防ぐ
# (ERR_PNPM_ABORTED_REMOVE_MODULES_DIR_NO_TTY の公式回避策)
ENV CI=true
RUN pnpm run build

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
