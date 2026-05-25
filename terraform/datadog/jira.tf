# =============================================================================
# Datadog Jira integration セットアップ手順
#
# 公式 Jira integration の install は Datadog UI で 1 回実施 (Terraform 化不可):
#
# 1. Datadog UI → Integrations → "Jira" → "Install Integration"
# 2. Atlassian site URL を入力 (例 https://your-org.atlassian.net)
# 3. Atlassian アカウントの email + API token を入力
#    (Atlassian: https://id.atlassian.com/manage-profile/security/api-tokens で発行)
# 4. "Issue Creation Defaults" を設定:
#    - Project: ${var.jira_project_key} と一致させる
#    - Issue type: Task / Bug / Incident のいずれか (運用方針による)
# 5. Save & Test (test issue が project に作成されれば成功)
#
# Terraform 側で扱うのは monitor message 内の @jira-<project_key> handle のみ。
# - Slack と異なり Jira channel 登録系の Terraform resource は存在しない (provider v3.x)。
# - monitor が critical 状態に遷移したタイミングで Jira ticket が自動作成され、
#   Datadog Triage と双方向 sync される (ack / resolve / 担当者 assign)。
#
# 動作:
# - var.jira_project_key == ""  → @jira-... は生成されず Jira 起票無効
# - var.jira_project_key != ""  → monitors.tf の {{#is_alert}} ブロックで起票
#
# 運用 Tip:
# - critical 時のみ起票 (warning では起票しない) は monitors.tf の local.jira_block で
#   {{#is_alert}} ... {{/is_alert}} ラップにより実現。oncall 疲労を抑える設計。
# - issue title は monitor 名がそのまま使われる。tag 由来の動的部分は
#   `{{container_name.name}}` などの template 変数を monitor 名に埋め込む。
# =============================================================================
