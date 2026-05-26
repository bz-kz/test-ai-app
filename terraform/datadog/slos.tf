# Datadog SLO 定義。設計の根拠は docs/superpowers/specs/2026-05-26-datadog-slo-design.md。
#
# 3 SLO + 3 SLO alert monitor:
# - backend_availability (metric-based)         + slo_alert_backend_availability
# - llm_latency          (time-slice)           + slo_alert_llm_latency
# - frontend_lcp         (metric-based, RUM)    + slo_alert_frontend_lcp
#
# 通知は monitors.tf の local.recipient_block + local.jira_block を流用。
# SLO threshold には warning 行を付けない (1-tier breach 方針、設計 §5)。

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
    numerator   = "sum:trace.backend.request.hits{service:backend,env:${var.env}}.as_count() - sum:trace.backend.request.errors{service:backend,env:${var.env}}.as_count()"
    denominator = "sum:trace.backend.request.hits{service:backend,env:${var.env}}.as_count()"
  }

  thresholds {
    timeframe = "7d"
    target    = 99.0
  }

  tags = concat(local.common_tags, ["category:slo", "sli:backend_availability"])
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

  tags = concat(local.common_tags, ["category:slo-alert", "sli:backend_availability"])
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

  tags = concat(local.common_tags, ["category:slo", "sli:llm_latency", "subsystem:llm"])
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

  tags = concat(local.common_tags, ["category:slo-alert", "sli:llm_latency", "subsystem:llm"])
}
