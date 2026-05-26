# ADR-0006 FE-015: frontend-browser RUM Application。
# applicationId / clientToken は output 経由で取得 → .env に転記。

resource "datadog_rum_application" "frontend_browser" {
  name = "${var.app_name}-frontend-browser"
  type = "browser"
}
