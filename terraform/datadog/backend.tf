# HCP Terraform (Terraform Cloud) backend.
# State 保管 + Datadog credentials (workspace env vars) を 1 箇所に集約する。
# Spec: docs/superpowers/specs/2026-05-26-datadog-iac-cicd-design.md
# ADR:  docs/adr/0007-iac-cd-via-github-actions.md
#
# <your-hcp-org> は operator が手で置換する placeholder。
# 置換手順は terraform/datadog/README.md の "CI/CD" 章参照。
terraform {
  cloud {
    organization = "<your-hcp-org>"
    workspaces { name = "test-ai-app-datadog" }
  }
}
