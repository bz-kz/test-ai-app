# Design: Datadog SLO 監視

- Date: 2026-05-26
- Status: Draft (brainstorming output, awaiting user review)
- Owner: bz-kz
- Related: ADR-0006 (observability via OTLP/OTel), `terraform/datadog/monitors.tf`, branch `016-datadog-docker-monitor-jira`

## 1. 目的

`terraform/datadog/` に **`datadog_service_level_objective`** リソースを足し、IaC で完結する SLO 監視パターンを確立する。Local-only PoC の延長として「本番化したら何を SLO 化するか」を予習する位置付けで、99.9% などの厳しい数値ターゲットは追わない。

## 2. 決定事項サマリ

| 項目           | 決定                                                                         | 根拠                                                                           |
| -------------- | ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| 目的           | IaC パターン確立 (PoC 練習)                                                  | local-only PoC、本番デプロイ無し                                               |
| 対象 SLI       | Backend availability / LLM /generate latency / Frontend LCP                  | user-journey の代表 3 点                                                       |
| Rolling window | 全て 7d                                                                      | 既存 monitor の「1 週でベースライン」と整合                                    |
| 通知           | SLO status alert のみ (burn rate 無し)                                       | PoC でアラート tier を増やす理由が薄い                                         |
| 通知ルート     | 既存 Slack/Jira pipeline 流用 (`local.recipient_block` + `local.jira_block`) | DRY、既存 monitor と挙動を揃える                                               |
| 実装方式       | Metric-based を基本 (Approach A)、LLM latency のみ time-slice                | LLM latency event-count には APM Span-Based Metric が必要で IaC 完結を崩すため |

## 3. ファイル配置

```
terraform/datadog/
├── slos.tf            ← 新規 (本 Block で追加)
├── monitors.tf        ← 既存。変更なし
├── dashboards.tf      ← 既存。本 Block では変更なし (D3 で deferred)
└── README.md          ← SLO 章を追記
```

**規約**:

- 既存 `local.common_tags` (env / app / team / managed-by) を流用
- SLO 固有 tag: `category:slo` + `sli:<name>` (例: `sli:backend_availability`)
- SLO 名: `[${var.app_name}] <SLI 名> 7d`
- SLO alert monitor 名: `[${var.app_name}] SLO breach — <SLI 名>`

## 4. SLO 定義

### 4.1 Backend availability — metric-based (event ratio)

```hcl
resource "datadog_service_level_objective" "backend_availability" {
  name        = "[${var.app_name}] backend availability 7d"
  type        = "metric"
  description = "Backend HTTP の success rate (5xx 以外) を 7d rolling で計測。既存 backend_5xx_rate monitor の SLI 版。"

  query {
    numerator   = "sum:trace.backend.request.hits{service:backend,env:${var.env}}.as_count() - sum:trace.backend.request.errors{service:backend,env:${var.env}}.as_count()"
    denominator = "sum:trace.backend.request.hits{service:backend,env:${var.env}}.as_count()"
  }

  thresholds {
    timeframe = "7d"
    target    = 99.0
  }

  tags = concat(local.common_tags, ["service:backend", "category:slo", "sli:backend_availability"])
}
```

- **Target 99%** = 7d で 1.68h ぶん 5xx 許容。
- 既存 `backend_5xx_rate` monitor と同一の trace metric を使用 — 新規依存は増えない。

### 4.2 LLM /generate latency — time-slice

```hcl
resource "datadog_service_level_objective" "llm_latency" {
  name        = "[${var.app_name}] LLM /generate p95 < 7min 7d"
  type        = "time_slice"
  description = "LLM 推論 p95 latency が 7 分 (420s) 未満である time slice の割合。INF-006: CPU 推論の通常 p95 = 4-5 分。"

  sli_specification {
    time_slice {
      query {
        formula { formula_expression = "query1" }
        query {
          metric_query {
            name  = "query1"
            query = "p95:trace.backend.request{service:backend,env:${var.env},resource_name:POST_/api/generate}"
          }
        }
      }
      comparator = "<"
      threshold  = 420000  # ms
    }
  }

  thresholds {
    timeframe = "7d"
    target    = 95.0
  }

  tags = concat(local.common_tags, ["service:backend", "category:slo", "sli:llm_latency", "subsystem:llm"])
}
```

- **Target 95%** = 7d 中 5% (≒ 8.4h) の "p95 > 7min" 状態を許容。CPU 推論 cold start を吸収。
- **type が time_slice** の理由は §6 Caveats C1 参照。

### 4.3 Frontend LCP — metric-based RUM event ratio

```hcl
resource "datadog_service_level_objective" "frontend_lcp" {
  name        = "[${var.app_name}] frontend LCP < 2500ms 7d"
  type        = "metric"
  description = "Frontend RUM view event のうち LCP < 2500ms の割合。Google Core Web Vital「Good」(p75 < 2500ms) に準拠。"

  query {
    numerator   = "sum:rum.lcp.good{service:frontend-browser,env:${var.env}}.as_count()"
    denominator = "sum:rum.lcp.total{service:frontend-browser,env:${var.env}}.as_count()"
  }

  thresholds {
    timeframe = "7d"
    target    = 75.0
  }

  tags = concat(local.common_tags, ["category:slo", "sli:frontend_lcp", "service:frontend-browser"])
}
```

- **Target 75%** = Core Web Vitals "Good" の p75 閾値定義に整合。
- `rum.lcp.good` / `rum.lcp.total` は本 Block 時点では **存在しない custom metric**。§6 C2 / §7 D2 参照。

## 5. 通知配線 (SLO alert monitors)

Datadog SLO リソース単体には alert 機能が無いため、`datadog_monitor` を `type = "slo alert"` で 3 本立てる。

**共通テンプレート**:

```hcl
resource "datadog_monitor" "slo_alert_backend_availability" {
  name    = "[${var.app_name}] SLO breach — backend availability"
  type    = "slo alert"
  message = <<-EOT
    Backend availability SLO (7d, target 99%) が割れました。
    5xx が長期的に増えている可能性 — 既存 monitor backend_5xx_rate と logs を見て探してください。
    ${local.recipient_block}
    ${local.jira_block}
  EOT

  query = "error_budget(\"${datadog_service_level_objective.backend_availability.id}\").over(\"7d\") > 100"

  monitor_thresholds {
    critical = 100
  }

  notify_no_data = false

  tags = concat(local.common_tags, ["category:slo-alert", "sli:backend_availability"])
}
```

**3 本立てるもの**:
| SLO | alert monitor | breach 時メッセージの調査リード |
|---|---|---|
| `backend_availability` | `slo_alert_backend_availability` | 既存 `backend_5xx_rate` monitor + logs |
| `llm_latency` | `slo_alert_llm_latency` | 既存 `llm_latency_p95` monitor + `llm_container_memory` |
| `frontend_lcp` | `slo_alert_frontend_lcp` | RUM Performance dashboard + browser console |

**ポリシー**:

- `message` に `${local.recipient_block}` + `${local.jira_block}` を埋め込み、Slack 全 transition / Jira critical-only を既存 monitor と揃える
- `query` は全て `error_budget("<id>").over("7d") > 100` (= budget 全消費で発火)
- `renotify_interval` は付けない (SLO breach は緩い tempo)
- `notify_no_data = false` (新規 SLO は 7d 経過まで no-data が普通)
- **Warning tier 無し** — burn rate 見送りの決定と整合 (1-tier breach のみ)

## 6. Caveats

| #   | Caveat                                                            | 影響                                       | 対処                                                      |
| --- | ----------------------------------------------------------------- | ------------------------------------------ | --------------------------------------------------------- |
| C1  | LLM latency は time-slice 型 (Approach A の event-count から逸脱) | SLO 3 本の type が揃わない                 | 本 doc §4.2 に理由明記。event-count 統一は D1 で deferred |
| C2  | `rum.lcp.good` / `rum.lcp.total` は存在しない custom metric       | LCP SLO が apply しても "No data"          | D2 で metric 生成。当面 placeholder で apply 可           |
| C3  | 新規 SLO は最初の 7d は "No data" / "Calculating"                 | 「壊れている」と誤認しがち                 | README に挙動を明記                                       |
| C4  | 既存 `backend_5xx_rate` の trace metric 前提に依存                | 既存 monitor が動かなければ SLO も動かない | 既存依存。新規問題ではない                                |
| C5  | `local` env 単独運用                                              | env 横断比較できない                       | local-only PoC 前提どおり。ADR 不要                       |

## 7. Deferred items

| ID  | 内容                                                                                                                        | 切り出し理由                                          |
| --- | --------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| D1  | APM Span-Based Metric で `backend.llm.requests.under_threshold` を生成し、LLM latency SLO を event-count 型に統一 (C1 解消) | Terraform 外設定が必要 / pattern doc 本筋から外れる   |
| D2  | RUM-derived metric で `rum.lcp.good` / `rum.lcp.total` を生成 (C2 解消)                                                     | RUM Analytics generate-metric の terraform 化を要調査 |
| D3  | Overview dashboard に SLO widget 追加                                                                                       | 視認性の問題で SLO 設計とは独立                       |
| D4  | Burn rate alert (Fast/Slow 2 tier)                                                                                          | PoC では見送り、本番化タイミングで再評価              |
| D5  | `prod` env 用 SLO の `environments/prod/` 分割                                                                              | 本番化タイミングで対応                                |

## 8. 適用後 verification

`local-deployment-discipline.md` §3 と同じ精神で、Block 完了後の手動確認:

```bash
cd terraform/datadog
terraform plan   # 3 SLO + 3 SLO alert monitor の追加のみ
terraform apply
```

Datadog UI 上で:

1. Service Reliability → SLO list に 3 件並ぶ
2. Monitors → SLO Alerts に 3 件並ぶ
3. 各 SLO の初期 status は "No data" / "Calculating" (C3)

Smoke (denominator にデータを 1 つ落とす):

1. `docker compose up -d`
2. ブラウザで `http://localhost:3000/` → frontend LCP の view event 1 件
3. `curl http://localhost:8000/health` → backend `trace.hits` 1 件
4. UI で `/api/generate` を 1 回呼ぶ → LLM latency 1 サンプル

Metrics Explorer で以下が 1 点でも見えれば配線 OK:

- `trace.backend.request.hits{env:local}`
- `p95:trace.backend.request{resource_name:POST_/api/generate,env:local}`
- `@view.largest_contentful_paint{service:frontend-browser,env:local}` (RUM Analytics)

## 9. ADR の要否

不要。既存 ADR-0006 (observability via OTLP/OTel) の派生実装に当たる。`terraform/datadog/` 内の追加リソースで完結し、§1 のネットワーク egress 制約や §2 のインフラ層境界に影響しない。

C1 (time-slice 逸脱) は ADR 規模ではなく、本 doc §4.2 / §6 / §7 D1 で記述する範囲で十分。

## 10. 設計を 1 段落で

Datadog Terraform に `slos.tf` を追加し、3 SLO (backend availability metric-based / LLM /generate latency time-slice / frontend LCP metric-based) を 7d rolling window で定義する。各 SLO に対応する SLO-alert monitor を 1 本ずつ立て、既存 `local.recipient_block` + `local.jira_block` を流用して Slack 全 transition / Jira critical-only の通知を再現する。LLM latency のみ time-slice 型を採用し event-count への統一は deferred、LCP の custom metric 生成も deferred とする。
