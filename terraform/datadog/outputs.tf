output "rum_application_id" {
  description = "frontend-browser RUM Application ID — .env の NEXT_PUBLIC_DD_RUM_APPLICATION_ID に転記"
  value       = datadog_rum_application.frontend_browser.id
}

output "rum_client_token" {
  description = "frontend-browser RUM Client Token — .env の NEXT_PUBLIC_DD_RUM_CLIENT_TOKEN に転記"
  value       = datadog_rum_application.frontend_browser.client_token
  sensitive   = true
}

output "rum_env_snippet" {
  description = "そのまま .env に貼れる形の RUM 設定スニペット"
  value       = <<-EOT
    NEXT_PUBLIC_RUM_ENABLED=true
    NEXT_PUBLIC_DD_RUM_APPLICATION_ID=${datadog_rum_application.frontend_browser.id}
    NEXT_PUBLIC_DD_RUM_CLIENT_TOKEN=${datadog_rum_application.frontend_browser.client_token}
    NEXT_PUBLIC_DD_SITE=ap1.datadoghq.com
    NEXT_PUBLIC_DD_RUM_SERVICE=frontend-browser
    NEXT_PUBLIC_DD_RUM_ENV=${var.env}
  EOT
  sensitive   = true
}
