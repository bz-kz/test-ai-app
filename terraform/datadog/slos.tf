# Datadog SLO 定義。設計の根拠は docs/superpowers/specs/2026-05-26-datadog-slo-design.md。
#
# 3 SLO + 3 SLO alert monitor:
# - backend_availability (metric-based)         + slo_alert_backend_availability
# - llm_latency          (time-slice)           + slo_alert_llm_latency
# - frontend_lcp         (metric-based, RUM)    + slo_alert_frontend_lcp
#
# 通知は monitors.tf の local.recipient_block + local.jira_block を流用。
# SLO threshold には warning 行を付けない (1-tier breach 方針、設計 §5)。
