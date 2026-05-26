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
- **SLO** (`slos.tf`) — 3 SLO + 3 SLO alert monitor。7d rolling、target は
  backend availability 99% / LLM /generate p95 < 7min 95% / frontend LCP < 2500ms 75%。
  通知は monitors.tf の critical tier と同じ Slack/Jira pipeline を流用 (warning tier 無し)。
  親 ADR は `docs/adr/0006-observability-via-otlp-otel.md`。具体的な SLI 選定・閾値・clean queries は `docs/superpowers/specs/2026-05-26-datadog-slo-design.md`。

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
- 新規 SLO は最初の 7d は "No data" / "Calculating" 表示が正常。Service Reliability
  ページで 7d 経過後に本値が出る。
- `frontend_lcp` SLO は `rum.lcp.good` / `rum.lcp.total` custom metric に依存。
  これらは RUM Analytics の Generate Metric で別 Block 作成 (spec D2)。
  未生成のうちは LCP SLO のみ恒久 "No data"。他 2 SLO は影響なし。
- LLM latency SLO は time-slice 型。event-count への統一は APM Span-Based Metric
  追加が必要 (spec D1) で deferred。
- `monitor_recipients` 未設定だと定義は作られるが通知が走らない (drill 用にあえて
  空のまま運用するパターンも可)。

## Drift 防止

Datadog UI で手動編集してしまうと terraform plan で drift が出る。UI 側で試作
→ JSON export → tf に転記の流れが安全。
