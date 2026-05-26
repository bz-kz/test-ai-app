# HCP Terraform (Terraform Cloud) backend.
# State 保管 + Datadog credentials (workspace env vars) を 1 箇所に集約する。
# Spec: docs/superpowers/specs/2026-05-26-datadog-iac-cicd-design.md
# ADR:  docs/adr/0007-iac-cd-via-github-actions.md
terraform {
  cloud {
    organization = "example-org-e62762"
    workspaces { name = "test-ai-app-datadog" }
  }
}
