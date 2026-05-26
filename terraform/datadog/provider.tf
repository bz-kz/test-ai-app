# Datadog Terraform provider — ADR-0006 補強。
# RUM Application / Service Catalog / Monitor / Dashboard を IaC で管理する。
#
# 認証: api_key (送信用) + app_key (管理 API 用) の 2 つが必要。
# Datadog UI → Organization Settings → Application Keys で app_key を発行。

terraform {
  required_version = ">= 1.7"
  required_providers {
    datadog = {
      source  = "DataDog/datadog"
      version = "~> 3.50"
    }
  }
}

provider "datadog" {
  # api_key / app_key は明示しない → provider が DD_API_KEY / DD_APP_KEY env var
  # を自動検出する。.env を shell に取り込んでから terraform を実行:
  #   set -a && source ../../.env && set +a && terraform plan
  # この方式で .env を二重管理しない (terraform.tfvars に secret を書かない)。
  api_url = var.datadog_api_url
}
