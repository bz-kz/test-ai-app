# Design: Datadog Terraform IaC CI/CD

- Date: 2026-05-26
- Status: Draft (brainstorming output, awaiting user review)
- Owner: bz-kz
- Related: ADR-0005 (agent push & PR policy), ADR-0006 (observability via OTLP/OTel), spec `2026-05-26-datadog-slo-design.md`, `terraform/datadog/`

## 1. 目的

`terraform/datadog/` の terraform apply を GitHub Actions 上で自動化する。PR 時は plan を sticky comment で提示、main へ merge されたタイミングで apply を実行。state は HCP Terraform (Terraform Cloud free tier) へ移管。Datadog だけが対象で、application stack (docker compose) は引き続き手元実行。

## 2. 決定事項サマリ

| 項目             | 決定                                                             | 根拠                                |
| ---------------- | ---------------------------------------------------------------- | ----------------------------------- |
| State backend    | HCP Terraform (Terraform Cloud) free tier                        | AWS 追加不要 / state lock + UI 込み |
| Workflow trigger | Plan on PR + Apply on push to main                               | 業界標準、レビュア視認性            |
| Approval gate    | 無し (`-auto-approve`)                                           | PoC、PR review 自体を承認とみなす   |
| Path filter      | `terraform/datadog/**` + workflow 自身                           | 関係ない PR で job が起動しない     |
| Secret 集約      | DD_API_KEY / DD_APP_KEY は HCP 側、GH には TF_API_TOKEN 1 個のみ | 集約点を 1 つに、漏洩面を縮小       |
| 対象範囲         | `terraform/datadog/` のみ。他の terraform は明示的 opt-in 要     | ADR-0007 で境界明記                 |

## 3. アーキテクチャ

```
┌─────────────────────┐                    ┌──────────────────┐
│  GitHub Actions     │  ─── plan ─────▶   │  HCP Terraform   │
│  (本リポジトリ)      │   apply           │   (state + vars) │
│                     │   ◀── state ───── │                  │
└──────────┬──────────┘                    └────────┬─────────┘
           │                                        │
           │  TF_API_TOKEN (secret)                 │  DD_API_KEY / DD_APP_KEY
           │                                        │  (workspace env vars)
           ▼                                        ▼
       PR plan job                            Datadog API (ap1)
       Merge apply job                         |
                                              ▼
                                         SLO / Monitor / Dashboard 反映
```

HCP Terraform は **state backend** と **secret 保管庫** の 2 役。Workflow は 1 ファイル / 2 job (`plan` / `apply`)。

## 4. Workflow ファイル

新規 `.github/workflows/terraform-datadog.yml`:

````yaml
name: terraform-datadog

on:
  pull_request:
    paths:
      - "terraform/datadog/**"
      - ".github/workflows/terraform-datadog.yml"
  push:
    branches: [main]
    paths:
      - "terraform/datadog/**"
      - ".github/workflows/terraform-datadog.yml"

permissions:
  contents: read
  pull-requests: write

env:
  TF_CLOUD_ORGANIZATION: "<your-hcp-org>"
  TF_WORKSPACE: "test-ai-app-datadog"
  TF_API_TOKEN: ${{ secrets.TF_API_TOKEN }}
  TF_IN_AUTOMATION: "true"

jobs:
  plan:
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: terraform/datadog
    steps:
      - uses: actions/checkout@v4

      - uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: "1.9"
          cli_config_credentials_token: ${{ secrets.TF_API_TOKEN }}

      - run: terraform fmt -check -recursive
      - run: terraform init
      - run: terraform validate
      - id: plan
        run: terraform plan -no-color -input=false
        continue-on-error: true

      - uses: marocchino/sticky-pull-request-comment@v2
        with:
          header: terraform-datadog-plan
          message: |
            ### terraform plan (datadog)
            ```
            ${{ steps.plan.outputs.stdout }}
            ```
            stderr (if any):
            ```
            ${{ steps.plan.outputs.stderr }}
            ```

      - if: steps.plan.outcome == 'failure'
        run: exit 1

  apply:
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: terraform/datadog
    steps:
      - uses: actions/checkout@v4

      - uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: "1.9"
          cli_config_credentials_token: ${{ secrets.TF_API_TOKEN }}

      - run: terraform init
      - run: terraform apply -auto-approve -input=false
````

**意図的な選択**:

- `cache` 無し (HCP mode では provider plugin が HCP 側で解決されるため効果薄)
- `terraform plan -out=...` artifact → apply 再利用 無し (HCP workspace 内で plan→apply が cohesion 保証されるため)
- Slack 通知 無し (Datadog monitor の通知と二重になる)
- Workflow ファイル自身を `paths:` に含める (workflow 変更時にも plan を走らせる)

## 5. Backend 切替

新規 `terraform/datadog/backend.tf`:

```hcl
terraform {
  cloud {
    organization = "<your-hcp-org>"
    workspaces { name = "test-ai-app-datadog" }
  }
}
```

## 6. Operator one-time セットアップ

CI が動き始める前に、人間オペレータが手で 1 回だけ実行する作業:

### 6.1 HCP Terraform 側

1. https://app.terraform.io/ サインアップ (GitHub ログイン可)
2. Organization 作成 (例: `bz-kz`)
3. Workspace 作成
   - Type: **CLI-driven workflow** (VCS 連携は使わない)
   - Name: `test-ai-app-datadog`
   - Terraform version: 1.9.x
4. Workspace → Variables で以下を登録:

   **Environment variables (Sensitive チェック)**:
   - `DD_API_KEY`
   - `DD_APP_KEY`

   **Terraform variables**:
   - `env = "local"`
   - `app_name = "test-ai-app"`
   - `owner_team = "bz-kz"`
   - `datadog_api_url = "https://api.ap1.datadoghq.com"`
   - `slack_account_name = "<DD-side slack account>"`
   - `slack_channels = ["#all-datadog-notify"]`
   - `monitor_recipients = []`
   - `jira_project_key = "<JIRA_KEY or empty>"`

5. User Settings → Tokens → API tokens を発行
6. 発行した token を GH repo の Settings → Secrets → Actions に `TF_API_TOKEN` として登録

### 6.2 Placeholder 置換 (リポジトリ側)

`<your-hcp-org>` 文字列が 2 箇所に残っているので、Section 6.1 で作った organization 名へ置換:

- `terraform/datadog/backend.tf` の `organization = "<your-hcp-org>"`
- `.github/workflows/terraform-datadog.yml` の `TF_CLOUD_ORGANIZATION: "<your-hcp-org>"`

```bash
# 例 (org 名が "bz-kz" の場合)
sed -i '' 's/<your-hcp-org>/bz-kz/g' terraform/datadog/backend.tf .github/workflows/terraform-datadog.yml
```

### 6.3 State 移行 (ローカル)

```bash
cd terraform/datadog
set -a && source ../../.env && set +a
export TF_TOKEN_app_terraform_io="<TF_API_TOKEN>"
terraform init -migrate-state    # ローカル tfstate を HCP へ uploads (yes プロンプト)
```

成功すると HCP workspace に既存 16 resources が登録される。ローカルの `terraform.tfstate` / `.backup` は不要に (`.gitignore` 維持で OK、削除可)。

### 6.4 検証

HCP workspace の "Resources" タブで 16+ リソースが表示されれば移行成功。

## 7. ADR-0007

新規 ADR が必要。理由 = `CLAUDE.md` §2 が「Local-only PoC、本番デプロイ無し」と明記しているのに、CI/CD で実 Datadog org に apply するのは方針の境界変更にあたる。

ADR core decision:

> Datadog Terraform に限り、PR merge を契機に GitHub Actions が `terraform apply` を実行する。State は HCP Terraform 上に置き、ローカルの `terraform.tfstate` は廃止する。Datadog 以外の terraform (将来追加されたら) は明示的に opt-in する別 workflow を要する — 本 ADR は `terraform/datadog/**` だけを CI/CD 対象に含める。

ADR-0005 / 0006 と同じく Status: Accepted + 関連 file 一覧を持つ形。

## 8. 障害モード

| シナリオ                             | 起きる事                                           | 対応                                                        |
| ------------------------------------ | -------------------------------------------------- | ----------------------------------------------------------- |
| HCP service down                     | plan/apply とも fail                               | GH Actions UI で再 run。HCP SLA 範囲                        |
| Datadog API rate limit               | apply 中に 429                                     | provider が自動 retry。連続失敗なら apply job fail で気付く |
| Plan sticky comment が >65k chars    | GitHub comment size limit                          | 当面素直に投げて溢れたら truncate 対応 (YAGNI)              |
| 同時 PR merge (apply 競合)           | HCP workspace の state lock で serialize           | 壊れない、遅くなるだけ                                      |
| `terraform/datadog/**` 外の PR merge | path filter で apply skip                          | 想定通り                                                    |
| TF_API_TOKEN leak                    | HCP CLI と `hashicorp/setup-terraform` が log mask | `echo $TF_API_TOKEN` 等を書かない discipline 必要           |
| Workflow file 変更が PR              | path filter に含めているので plan 走る             | semantic 妥当性は merge 後の実走で初検証 (GH Actions 限界)  |

## 9. Provider auth の挙動

Datadog provider は `DD_API_KEY` / `DD_APP_KEY` の env を自動読み取り (`provider.tf:18` のコメント参照)。HCP workspace で "Environment variable" カテゴリ + Sensitive で登録すると Terraform プロセスに env として注入され、provider が拾う。GH Actions 側で何もしない。

検証ポイント:

- HCP workspace Variables ページで `DD_API_KEY` / `DD_APP_KEY` が **Category: Environment variable** (Terraform variable ではない) で登録
- 両方 Sensitive チェック

## 10. Rollback

1. **Forward fix (基本)**: 変更を打ち消す PR を切って merge → 再 apply で前状態へ
2. **HCP workspace から手動 rollback (emergency)**: HCP Runs ページに過去 plan/apply の履歴あり、過去 state を current にする操作が UI で可能

PoC では 1 を基本にする。

## 11. Caveats

| #   | Caveat                                                                              | 対処                                                |
| --- | ----------------------------------------------------------------------------------- | --------------------------------------------------- |
| C1  | HCP free tier の将来制限                                                            | S3 backend へ swap する逃げ道あり (ADR 改訂要)      |
| C2  | State 移行は不可逆寄り (戻すのが面倒)                                               | README に checklist 化                              |
| C3  | `-auto-approve` apply の危険性                                                      | GH branch protection (D1) で PR review 必須化を推奨 |
| C4  | HCP workspace Variables を UI 手動管理 (Terraform 化されない鶏卵)                   | `hashicorp/tfe` provider で更 IaC 化可能だが YAGNI  |
| C5  | sticky-pull-request-comment は外部 Action 依存                                      | 代替豊富、止まったら swap                           |
| C6  | 既存 pre-existing drift 2 件 (`overview` / `error_log_spike`) は state 移行後も残る | 別 Block で drift 解消                              |

## 12. Deferred items

| ID  | 内容                                                                            | 切り出し理由                                             |
| --- | ------------------------------------------------------------------------------- | -------------------------------------------------------- |
| D1  | GitHub branch protection rule (main 直 push 禁止、PR 必須、status check 緑必須) | UI 設定のみ、本 Block は workflow を置くことが目的で独立 |
| D2  | Drift detection cron (毎日 plan、差分あれば issue/Slack)                        | あったら良いが必須でない                                 |
| D3  | Speculative plan (HCP VCS-driven mode への乗り換え)                             | CLI-driven で十分                                        |
| D4  | Workflow テスト (`act` で local 実行)                                           | nice-to-have、PR 1 本で検証可                            |
| D5  | 複数 environments (`local` / `prod` workspace 分離)                             | 本番化のタイミングで対応                                 |

## 13. 本 Block の作業範囲

**やること** (Block 内で commit):

- `terraform/datadog/backend.tf` 新規
- `.github/workflows/terraform-datadog.yml` 新規
- `terraform/datadog/README.md` 更新 (CI/CD 章追記)
- `docs/adr/0007-iac-cd-via-github-actions.md` 新規
- 既存 spec `2026-05-26-datadog-slo-design.md` §8 (Verification) の文言を「CI で自動 apply される」前提に更新

**やらないこと** (operator 手作業):

- HCP organization / workspace / variables 作成
- GH Actions secret `TF_API_TOKEN` 設定
- `terraform init -migrate-state` 実行

## 14. 設計を 1 段落で

`terraform/datadog/` の state を HCP Terraform free tier に移管し、`.github/workflows/terraform-datadog.yml` で PR 時に sticky-comment plan、main merge 時に `-auto-approve` apply を実行する。Datadog credentials を含む全変数は HCP workspace 側に登録、GH Actions に渡す secret は `TF_API_TOKEN` 1 個のみ。Auto-apply の安全網は PR review (GH branch protection は deferred)、rollback は forward fix 基本。Datadog 以外の terraform は明示的 opt-in を要する境界を ADR-0007 で固定する。
