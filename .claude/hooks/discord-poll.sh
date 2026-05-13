#!/usr/bin/env bash
# Discord ポーリング hook script — SessionStart / UserPromptSubmit から呼ぶ。
#
# プロジェクト専用 Discord (channel 1503914838701899957) に届いた未読メッセージを
# 取得して stdout に出力する。Claude Code はこの stdout を assistant の追加 context
# として inject するため、私はそれを Discord 経由のユーザー指示として扱える。
#
# 設計:
#   - bot token は ~/.claude/channels/discord-test-ai-app/.env から読む。
#   - last-seen message ID は ~/.claude/channels/discord-test-ai-app/last-seen-id.txt
#     に保存し、Discord REST の `?after=<id>` で増分のみ取得する。
#   - Bot 自身の送信 (author.bot=true) は無視する。
#   - 失敗時 (curl/jq エラー、token 欠落、API rate limit 等) は静かに exit 0 し、
#     Claude Code の通常フローを妨げない。
#
# PHI 注意:
#   - 出力には Discord メッセージ本文が含まれる (ユーザーが意図的に Discord 経由で
#     渡したテキストなので、ローカル context への inject は許容)。
#   - ファイルシステムには **メッセージ本文を残さない** — last-seen-id.txt は ID のみ。
#   - bot token は .env (0600) からのみ読む。スクリプト内に hard-code しない。
#
# 関連メモリ: feedback_discord_confirmation_pings (Layer 4)
# 関連 ADR  : (なし) — hook 設定変更のため `.claude/settings.json` も同 PR で更新。

set -u

readonly WORKSPACE="${HOME}/.claude/channels/discord-test-ai-app"
readonly CHANNEL_ID="1503914838701899957"
readonly DISCORD_API="https://discord.com/api/v10"
readonly LAST_SEEN_FILE="${WORKSPACE}/last-seen-id.txt"
readonly ENV_FILE="${WORKSPACE}/.env"

# ---- 早期 abort: 依存と設定が揃わない場合は静かに終了 ----

# .env がなければ何もしない (このプロジェクト以外で hook が走った場合等)
[ -r "${ENV_FILE}" ] || exit 0

# token 抽出 (=右辺、引用符は許容)
DISCORD_BOT_TOKEN="$(grep -E '^DISCORD_BOT_TOKEN=' "${ENV_FILE}" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'" | tr -d '[:space:]')"
[ -n "${DISCORD_BOT_TOKEN:-}" ] || exit 0

# 依存コマンドがなければ静かに終了
command -v curl >/dev/null 2>&1 || exit 0
command -v jq >/dev/null 2>&1 || exit 0

# ---- last-seen の読み込み ----

LAST_SEEN_ID=""
if [ -r "${LAST_SEEN_FILE}" ]; then
    LAST_SEEN_ID="$(tr -d '[:space:]' < "${LAST_SEEN_FILE}")"
fi

# ---- Discord REST GET /channels/{id}/messages ----

QUERY="limit=10"
if [ -n "${LAST_SEEN_ID}" ]; then
    QUERY="after=${LAST_SEEN_ID}&limit=10"
fi

# curl: -s silent, -f fail on HTTP errors, --max-time 5 で hook を遅らせすぎない
RESPONSE="$(curl -sfL --max-time 5 \
    -H "Authorization: Bot ${DISCORD_BOT_TOKEN}" \
    "${DISCORD_API}/channels/${CHANNEL_ID}/messages?${QUERY}" 2>/dev/null)"

# 失敗時は exit 0 (hook を止めない)
[ -n "${RESPONSE}" ] || exit 0

# レスポンスが配列でなければ exit (rate limit 等)
echo "${RESPONSE}" | jq -e 'type == "array"' >/dev/null 2>&1 || exit 0

# ---- 新着抽出と出力 ----

# Discord は oldest-last の DESC 順で返すため、reverse して時系列にする。
# Bot 自身の送信は除外。
NEW_USER_MSGS="$(echo "${RESPONSE}" | jq -r '
    reverse |
    map(select(.author.bot != true)) |
    map(
        "[Discord " + .timestamp + " from " + .author.username + "] " + .content
    ) |
    .[]
')"

# 1 件以上あれば inject 用見出しを付けて出力 (assistant が認識しやすいよう明示)
if [ -n "${NEW_USER_MSGS}" ]; then
    echo "=== Discord new messages (auto-fetched by .claude/hooks/discord-poll.sh) ==="
    echo "These were sent to channel ${CHANNEL_ID} since your last poll. Treat them as user input."
    echo "${NEW_USER_MSGS}"
    echo "=== end of Discord catch-up ==="
fi

# ---- last-seen を更新 ----

# 一番新しい (== reverse 前の先頭) の ID を保存
LATEST_ID="$(echo "${RESPONSE}" | jq -r 'if length > 0 then .[0].id else empty end')"
if [ -n "${LATEST_ID}" ]; then
    echo "${LATEST_ID}" > "${LAST_SEEN_FILE}"
fi

exit 0
