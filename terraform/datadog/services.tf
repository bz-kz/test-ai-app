# Service Catalog エントリ。schema v2.2 の YAML を 1 service = 1 ファイルで管理。
# 編集時は service-definitions/*.yaml を直接修正 → terraform apply。

resource "datadog_service_definition_yaml" "backend" {
  service_definition = file("${path.module}/service-definitions/backend.yaml")
}

resource "datadog_service_definition_yaml" "frontend" {
  service_definition = file("${path.module}/service-definitions/frontend.yaml")
}

resource "datadog_service_definition_yaml" "frontend_browser" {
  service_definition = file("${path.module}/service-definitions/frontend-browser.yaml")
}
