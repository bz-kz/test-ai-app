# Datadog SLO 定義。設計の根拠は docs/superpowers/specs/2026-05-26-datadog-slo-design.md。
#
# 3 SLO + 3 SLO alert monitor:
# - backend_availability (metric-based)         + slo_alert_backend_availability
# - llm_latency          (time-slice)           + slo_alert_llm_latency
# - frontend_lcp         (time-slice, RUM)      + slo_alert_frontend_lcp
#
# 通知は monitors.tf の local.recipient_block + local.jira_block を流用。
# SLO threshold には warning 行を付けない (1-tier breach 方針、設計 §5)。
#
# -- ライフサイクル方針 (全 3 SLO + monitor ペアに統一適用) -------------------
# Datadog API には 2 つの制約があり、SLO の type 変更等で destroy + create が
# 必要になった際にナイーブな apply 順では失敗する:
#   (1) SLO が monitor から参照されている間は destroy できない (409 Conflict)
#   (2) "slo alert" 型 monitor の SLO ID は immutable (update 不可、400)
# 制約 (1)+(2) を同時に満たす apply 順は:
#   新 SLO 作成 → 新 monitor 作成 (新 SLO ID 参照) → 旧 monitor destroy → 旧 SLO destroy
# これを terraform 上で実現するため、3 SLO すべてに create_before_destroy、
# 3 monitor すべてに create_before_destroy + replace_triggered_by を付与。
# 詳細は PR #21 / #22 / 本 PR の commit message と PR description 参照。

# ----------------------------------------------------------------------------
# SLO: Backend availability (5xx 以外の success rate ≥ 99% / 7d)
# ----------------------------------------------------------------------------
# query は既存 backend_5xx_rate monitor と同じ trace metric を使用。
# trace metric が流れ始めるまでは "No data" のままだが apply は通る。
resource "datadog_service_level_objective" "backend_availability" {
  name        = "[${var.app_name}] backend availability 7d"
  type        = "metric"
  description = "Backend HTTP の success rate (5xx 以外) を 7d rolling で計測。既存 backend_5xx_rate monitor の SLI 版。"

  query {
    numerator   = "sum:trace.opentelemetry.instrumentation.fastapi.server.hits{service:backend,env:local}.as_count() - sum:trace.opentelemetry.instrumentation.fastapi.server.errors{service:backend,env:local}.as_count()"
    denominator = "sum:trace.opentelemetry.instrumentation.fastapi.server.hits{service:backend,env:local}.as_count()"
  }

  thresholds {
    timeframe = "7d"
    target    = 99.0
  }

  tags = concat(local.common_tags, ["service:backend", "category:slo", "sli:backend_availability"])

  lifecycle {
    create_before_destroy = true # ファイル冒頭「ライフサイクル方針」参照
  }
}

# ----------------------------------------------------------------------------
# Alert: backend_availability SLO breach
# ----------------------------------------------------------------------------
resource "datadog_monitor" "slo_alert_backend_availability" {
  name    = "[${var.app_name}] SLO breach — backend availability"
  type    = "slo alert"
  message = <<-EOT
    Backend availability SLO (7d, target 99%) が割れました。
    5xx が長期的に増えている可能性 — 既存 monitor backend_5xx_rate と logs を見て原因を探してください。
    ${local.recipient_block}
    ${local.jira_block}
  EOT

  query = "error_budget(\"${datadog_service_level_objective.backend_availability.id}\").over(\"7d\") > 100"

  monitor_thresholds {
    critical = 100
  }

  notify_no_data = false

  tags = concat(local.common_tags, ["service:backend", "category:slo-alert", "sli:backend_availability"])

  lifecycle {
    create_before_destroy = true
    replace_triggered_by  = [datadog_service_level_objective.backend_availability]
  }
}

# ----------------------------------------------------------------------------
# SLO: LLM /generate p95 latency < 7 分 (time-slice)
# ----------------------------------------------------------------------------
# Approach A (metric-based event-count) は APM Span-Based Metric が必要で
# IaC 完結を崩すため、ここだけ time_slice 型を採用。設計 §4.2 / Caveat C1。
# INF-006: CPU 推論の通常 p95 = 4-5 分 (~300s)、+50% で alert に揃える。
resource "datadog_service_level_objective" "llm_latency" {
  name        = "[${var.app_name}] LLM /generate p95 < 7min 7d"
  type        = "time_slice"
  description = "LLM 推論 p95 latency が 7 分 (420s) 未満である time slice の割合。INF-006: CPU 推論の通常 p95 = 4-5 分。"

  sli_specification {
    time_slice {
      query {
        formula {
          formula_expression = "query1"
        }
        query {
          metric_query {
            name  = "query1"
            query = "p95:trace.backend.request{service:backend,env:${var.env},resource_name:POST_/api/generate}"
          }
        }
      }
      comparator = "<"
      threshold  = 420000 # ms
    }
  }

  thresholds {
    timeframe = "7d"
    target    = 95.0
  }

  tags = concat(local.common_tags, ["service:backend", "category:slo", "sli:llm_latency", "subsystem:llm"])

  lifecycle {
    create_before_destroy = true # ファイル冒頭「ライフサイクル方針」参照
  }
}

# ----------------------------------------------------------------------------
# Alert: llm_latency SLO breach
# ----------------------------------------------------------------------------
resource "datadog_monitor" "slo_alert_llm_latency" {
  name    = "[${var.app_name}] SLO breach — LLM /generate latency"
  type    = "slo alert"
  message = <<-EOT
    LLM /generate latency SLO (7d, p95 < 7min target 95%) が割れました。
    確認: 既存 monitor llm_latency_p95 / llm_container_memory、ホスト CPU 占有、Ollama keep_alive。
    ${local.recipient_block}
    ${local.jira_block}
  EOT

  query = "error_budget(\"${datadog_service_level_objective.llm_latency.id}\").over(\"7d\") > 100"

  monitor_thresholds {
    critical = 100
  }

  notify_no_data = false

  tags = concat(local.common_tags, ["service:backend", "category:slo-alert", "sli:llm_latency", "subsystem:llm"])

  lifecycle {
    create_before_destroy = true
    replace_triggered_by  = [datadog_service_level_objective.llm_latency]
  }
}

# ----------------------------------------------------------------------------
# SLO: Frontend LCP < 2500ms (Google Core Web Vital "Good")
# ----------------------------------------------------------------------------
# RUM 自動生成メトリクス (rum.measure.view.largest_contentful_paint) を直接
# 参照する Time Slice SLO。カスタムメトリクスの生成は不要。
# p75 LCP が 2500ms 未満の time slice を "uptime" として計測する。
resource "datadog_service_level_objective" "frontend_lcp" {
  name        = "[${var.app_name}] frontend LCP < 2500ms 7d"
  type        = "time_slice"
  description = "Frontend RUM view の p75 LCP が 2500ms 未満であるかを Time Slice で計測。Google Core Web Vital「Good」(p75 < 2500ms) に準拠。"

  sli_specification {
    time_slice {
      query {
        formula {
          formula_expression = "query1"
        }
        query {
          metric_query {
            name        = "query1"
            query       = "p75:rum.measure.view.largest_contentful_paint{service:frontend-browser,env:${var.env}}"
            data_source = "metrics"
          }
        }
      }
      comparator = "<"
      threshold  = 2500000000 # 2500ms = 2,500,000,000 ns（メトリクス単位: nanosecond）
    }
  }

  thresholds {
    timeframe = "7d"
    target    = 75.0
  }

  tags = concat(local.common_tags, ["category:slo", "sli:frontend_lcp", "service:frontend-browser"])

  lifecycle {
    create_before_destroy = true # ファイル冒頭「ライフサイクル方針」参照
  }
}

# ----------------------------------------------------------------------------
# Alert: frontend_lcp SLO breach
# ----------------------------------------------------------------------------
# Time Slice SLO は error_budget / burn_rate アラートの両方に対応。
resource "datadog_monitor" "slo_alert_frontend_lcp" {
  name    = "[${var.app_name}] SLO breach — frontend LCP"
  type    = "slo alert"
  message = <<-EOT
    Frontend LCP SLO (7d, target 75% of time slices with p75 LCP < 2500ms) が割れました。
    確認: RUM Performance dashboard、最近の frontend deploy、画像/フォント遅延、サードパーティ script。
    ${local.recipient_block}
    ${local.jira_block}
  EOT

  query = "error_budget(\"${datadog_service_level_objective.frontend_lcp.id}\").over(\"7d\") > 100"

  monitor_thresholds {
    critical = 100
  }

  notify_no_data = false

  tags = concat(local.common_tags, ["category:slo-alert", "sli:frontend_lcp", "service:frontend-browser"])

  lifecycle {
    create_before_destroy = true
    replace_triggered_by  = [datadog_service_level_objective.frontend_lcp]
  }
}
