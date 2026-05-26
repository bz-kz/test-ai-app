# AI Medical Generator overview dashboard。
# 仕様は dashboards/overview.json で管理 (Datadog UI で編集 → Export to JSON → ここに反映)。
# HCL widget block を直接書くよりも apm_resource_stats / spans data source を素直に
# 表現できるため、ADR-0006 の OTel + RUM 構成では JSON 方式を採用。
#
# 編集フロー:
#  1. Datadog UI で対象 dashboard を編集
#  2. Settings → Export to JSON
#  3. dashboards/overview.json を上書き
#  4. terraform apply で drift 解消

resource "datadog_dashboard_json" "overview" {
  dashboard = file("${path.module}/dashboards/overview.json")
}
