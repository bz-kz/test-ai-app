# =============================================================================
# Datadog Slack integration channel 登録
#
# 前提:
# - Slack workspace の OAuth install は UI で 1 回実施済 (Configure → Add a workspace)。
#   この step は Terraform で再現不可 (Slack OAuth が人間操作必須)。
# - 本ファイルは install 後の「Channels available for monitor alerts」へ channel を
#   登録 + 通知 payload の表示要素 (snapshot/tags 等) を管理する。
#
# 使い回し:
# - 他プロジェクトへ移植する場合、tf コードはそのままコピー。各プロジェクトで:
#   1. Datadog UI で対象 workspace に Slack OAuth install
#   2. terraform.tfvars に slack_account_name と slack_channels を設定
#   3. terraform apply
#
# ⚠️ Drift:
# - UI で手動 channel 追加すると次の terraform apply で削除される。channel 管理は
#   Terraform に一元化すること (UI 側は触らない運用に統一)。
# =============================================================================

resource "datadog_integration_slack_channel" "this" {
  for_each = toset(var.slack_channels)

  account_name = var.slack_account_name
  channel_name = each.value

  display {
    message  = true # monitor 本文を表示
    snapshot = true # グラフのスナップショット画像を添付
    tags     = true # monitor tag を表示
    notified = true # @-mention を有効化
  }
}
