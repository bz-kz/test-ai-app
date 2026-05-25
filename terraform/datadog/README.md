# terraform/datadog/

ADR-0006 補強。Datadog の RUM Application / Service Catalog / Monitors / Dashboard
を IaC で管理する。

## 含まれるリソース

- **RUM Application** (`rum.tf`) — `${app_name}-frontend-browser`。output 経由で
  applicationId / clientToken を取得し `.env` に転記する。
- **Service Catalog** (`services.tf` + `service-definitions/*.yaml`) — `backend`,
  `frontend`, `frontend-browser` の 3 service。schema v2.2。
- **Monitors** (`monitors.tf`) — backend 5xx rate / 各種 latency p95 / container
  CPU・memory saturation / restart loop / error log spike など。通知は Slack
  (warning + critical) + Jira (critical のみ、`var.jira_project_key` 設定時)。
- **Jira integration** (`jira.tf`) — Atlassian API token 登録は Datadog UI で 1 回
  実施 (Terraform 化不可)。Terraform 側は `var.jira_project_key` の有無で monitor
  message 内の `@jira-<project>` handle を on/off するのみ。詳細手順は `jira.tf`。
- **Dashboard** (`dashboards.tf`) — RUM + backend APM + LLM/ASR latency の
  3 グループ overview。

## 前提

- Terraform ≥ 1.7
- `DataDog/datadog` provider 3.50+
- `.env` に `DD_API_KEY` と `DD_APP_KEY` の両方
  - `DD_API_KEY` は送信用 (DD Agent 等と共用)
  - `DD_APP_KEY` は管理 API 用。Datadog UI → Organization Settings → Application Keys で発行
- `DD_SITE` に応じた API URL を `terraform.tfvars` で指定 (default `https://api.ap1.datadoghq.com`)

## 使い方

```bash
cd terraform/datadog
cp terraform.tfvars.example terraform.tfvars   # api_url / env / monitor_recipients を編集

# .env を shell に取り込む (DD_API_KEY / DD_APP_KEY を provider に渡す)
set -a && source ../../.env && set +a

terraform init
terraform plan
terraform apply

# RUM credentials を .env へ転記 (-raw で機密値が標準出力)
terraform output -raw rum_env_snippet >> ../../.env
```

`.env` の読み込みは shell ごとに必要。direnv を使っていれば `.envrc` で自動化可能。

## State

- Backend: local (`terraform.tfstate`)。PoC スコープのため remote 化していない。
- `.gitignore` で state ファイル + `*.tfvars` を commit 除外。

## 既知の調整ポイント

- `monitors.tf` の trace metric 名 (`trace.fastapi.request.hits` 等) は実 trace が
  流れ始めてから実値に合わせて修正する。OTel→Datadog の場合 metric 名が
  `trace.<integration>.*` ではなく resource span ベースになることがある。
- `dashboards.tf` も同様に metric 名要調整。
- Monitor 閾値は仮置き。1 週間のベースライン取得後に tighten 推奨。
- `monitor_recipients` 未設定だと定義は作られるが通知が走らない (drill 用にあえて
  空のまま運用するパターンも可)。

## Drift 防止

Datadog UI で手動編集してしまうと terraform plan で drift が出る。UI 側で試作
→ JSON export → tf に転記の流れが安全。
