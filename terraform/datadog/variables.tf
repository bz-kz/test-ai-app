variable "datadog_api_url" {
  description = "Datadog API URL — DD_SITE 由来。AP1 (東京) = https://api.ap1.datadoghq.com"
  type        = string
  default     = "https://api.ap1.datadoghq.com"
}

variable "env" {
  description = "Datadog env tag — local / staging / prod"
  type        = string
  default     = "local"
}

variable "app_name" {
  description = "アプリ名タグ (Service Catalog, monitor tag 等で共通使用)"
  type        = string
  default     = "test-ai-app"
}

variable "owner_team" {
  description = "オーナーチーム名 (Service Catalog 表示用)"
  type        = string
  default     = "ai-medical"
}

variable "repo_url" {
  description = "リポジトリ URL (Service Catalog の Source link)"
  type        = string
  default     = "https://github.com/bz-kz/test-ai-app"
}

variable "monitor_recipients" {
  description = "Slack 以外の追加通知先 (Datadog @-handle / email)。例 [\"@kodaira@bz-kz.com\", \"@pagerduty-oncall\"]。Slack は var.slack_channels から自動生成されるので不要。"
  type        = list(string)
  default     = []
}

# ---------------------------------------------------------------------------
# Slack integration (アプローチ A: OAuth は UI で 1 回、channel 登録は Terraform)
# ---------------------------------------------------------------------------

variable "slack_account_name" {
  description = "Datadog Slack integration の account name (UI: Configure → Slack account name の値、dash なし)。OAuth install 完了後に固定。例 \"datadognotify\"。"
  type        = string
  default     = ""
}

variable "slack_channels" {
  description = "Datadog から通知する Slack channel 名のリスト (# 必須)。例 [\"#all-datadog-notify\", \"#incident-1\"]。空配列で Slack 通知無効。"
  type        = list(string)
  default     = []
}

# ---------------------------------------------------------------------------
# Jira integration (アプローチ: Atlassian API token は UI で 1 回登録、
# monitor message 内の @-handle のみ Terraform 管理)
# ---------------------------------------------------------------------------

variable "jira_project_key" {
  description = "Datadog から ticket 起票する Jira project key (例 \"OPS\" / \"MEDREC\")。空文字で Jira 起票無効。UI で integration install 済が前提 (詳細は jira.tf 参照)。"
  type        = string
  default     = ""
}
