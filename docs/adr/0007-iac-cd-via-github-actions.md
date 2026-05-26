# ADR 0007: Datadog Terraform CI/CD via GitHub Actions (Datadog のみ opt-in)

- **Status:** Accepted
- **Date:** 2026-05-26
- **Owner:** Planner (Claude Opus 4.7)
- **Related Spec:** `docs/superpowers/specs/2026-05-26-datadog-iac-cicd-design.md`

## Context

`CLAUDE.md` §2 が「Local-only PoC、リモート / staging / production のデプロイ先は無い」と明記している。一方で `terraform/datadog/` だけは実 Datadog SaaS org を変更するため、apply は事実上「リモートに対する操作」になっており、手元 `terraform apply` の発火は人間オペレータの記憶頼みになっていた (Task 6 が SLO Block で operator-driven のまま残っているのが象徴例)。

放置すると 2 つのリスクが固定化する:

1. **Apply 忘れ** — SLO / monitor の追加が commit されたが apply されない状態が長期化し、コードと現実の Datadog org が divergence する。
2. **手元 state の単一障害点** — `terraform.tfstate` が 1 人の laptop にしかなく、紛失 = 既存 16 resources の管理不能。

CI/CD 化により両方の risk を畳む。同時に application stack (docker compose) は引き続き local-only という制約を保つ必要があり、すべての terraform を CI/CD 化する判断ではない。

## Decision

We will automate `terraform apply` for `terraform/datadog/` only via GitHub Actions on PR merge to `main`, with state hosted on HCP Terraform (Terraform Cloud) free tier. All other terraform stacks (現状存在しないが将来追加されたら) MUST opt-in by adding their own dedicated workflow file; the `terraform-datadog.yml` workflow is path-filtered to `terraform/datadog/**` only and does not generalize.

具体的に:

- **State backend**: HCP Terraform free tier、CLI-driven workspace `test-ai-app-datadog`。ローカル `terraform.tfstate` は廃止 (gitignore は維持)。
- **Trigger**: `pull_request` で `plan` job (sticky comment 投稿)、`push` to `main` で `apply -auto-approve` job。両方とも `paths:` filter で `terraform/datadog/**` と workflow 自身に限定。
- **Secret 集約**: Datadog 認証 (`DD_API_KEY` / `DD_APP_KEY`) は HCP workspace の env vars に格納。GH Actions secrets は `TF_API_TOKEN` 1 個のみ。
- **Approval gate**: 無し (`-auto-approve`)。安全網は PR レビュー時の sticky comment plan 確認。GitHub branch protection (main へ直 push 禁止・PR 必須・status check 緑必須) は別途設定推奨 (本 ADR の scope 外、deferred)。
- **適用範囲**: `terraform/datadog/**` のみ。他 terraform (例: 将来 `terraform/aws/`、`terraform/k8s/`) は本 workflow の対象外で、追加時には別 ADR + 別 workflow を要する。

## Consequences

- **Positive:**
  - Apply 忘れが構造的に発生しない (merge = apply)。
  - State の単一障害点解消、HCP UI で履歴 / drift 視認可能。
  - PR レビュー時に plan 差分が見える (auto-comment)、レビュアの認知負荷低減。
  - Datadog credentials が HCP に集約され、`.env` 配布や `terraform.tfvars` 共有が不要に。
- **Negative:**
  - 外部依存が 2 つ増える (HCP Terraform、GH Actions)。HCP free tier の将来制限 / sticky-pull-request-comment action の保守状況 がリスク。
  - `-auto-approve` のため、危険な変更を含む PR を不注意で merge すると即時反映される (mitigation: PR レビュー必須化を branch protection で)。
  - State 移行 (`init -migrate-state`) は逆方向の運用が手間 (HCP → local) なので、HCP からの離脱はコスト中。
  - HCP workspace variables の管理が Terraform 外 (HCP UI の手動) に逃げる「鶏卵」が発生する。
- **Reversibility:**
  - **Moderate**。HCP workspace の state を `terraform state pull` でローカルへ取り出し、`backend.tf` を削除して `terraform init -migrate-state` で local backend へ戻すことは技術的には可能。ただし HCP workspace variables の手動退避が必要。

## Alternatives considered

- **S3 + DynamoDB backend**: AWS アカウントが必要。本プロジェクトは AWS を一切使っておらず、CI/CD のためだけに導入するのは過剰。
- **GitHub Actions artifact に tfstate を載せる**: state lock が無いため並列 PR merge で破損リスク。PoC の 1 人作業でも不採用とした。
- **Plan-on-PR のみ、apply は引き続き手元**: 「apply 忘れ」リスクを構造的に解消できないため不採用。User が "PR マージのタイミングで apply" を明示要請。
- **すべての terraform を CI/CD 化する**: 現状 `terraform/` 配下に他 stack は無く、将来追加時に同じ pattern をテンプレートとして使えるが、本 ADR の意思決定範囲を超える。明示 opt-in 方式とした。
- **GitHub Environment protection (required reviewer)**: PoC 1 人作業では「自分で自分を承認」のセレモニーになるため見送り。本番化時に再評価。

## Gates affected

なし。本 ADR は CI/CD pipeline の追加であり、DoD gates G0–G7 のいずれの bar も変更しない。SLO Block の Verification gate (G6 / G7) は「`terraform apply` が CI で走った後 Datadog UI で SLO が見える」という運用前提に置き換わるが、gate そのものは無変更。

## Open follow-ups

- [ ] GitHub branch protection rule (main 直 push 禁止、PR 必須、status check 緑必須) — `auto-approve` の安全網として推奨。本 ADR では UI 操作のため scope 外。
- [ ] Drift detection cron — 毎日 1 回 `terraform plan` を流して差分があれば issue / Slack 通知。任意。
- [ ] 複数 environments (`local` / `prod` workspace 分離) — 本番化時に対応。
- [ ] `terraform-datadog.yml` の workflow テスト (`act` で local 実行) — nice-to-have。
