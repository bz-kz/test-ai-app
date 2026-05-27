# Datadog Terraform IaC CI/CD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `terraform/datadog/` の terraform apply を GitHub Actions で自動化する。PR で plan を sticky comment、main merge で apply。State は HCP Terraform (Terraform Cloud) free tier に移管。

**Architecture:** HCP Terraform を state backend + secret 保管庫 として使用 (Datadog credentials は HCP workspace 側に格納)。GH Actions に渡す secret は `TF_API_TOKEN` 1 個のみ。Workflow は 1 ファイル / 2 job 構成 (plan / apply)。Datadog 以外の terraform は明示的 opt-in が必要 — ADR-0007 で境界を固定。

**Tech Stack:** GitHub Actions, HCP Terraform (CLI-driven workspace mode), `hashicorp/setup-terraform@v3`, `marocchino/sticky-pull-request-comment@v2`, Terraform 1.9.x, DataDog/datadog provider ~> 3.50.

**Spec:** [`docs/superpowers/specs/2026-05-26-datadog-iac-cicd-design.md`](../specs/2026-05-26-datadog-iac-cicd-design.md)

---

## File Structure

```
.github/workflows/terraform-datadog.yml                      ← CREATE
terraform/datadog/backend.tf                                 ← CREATE
terraform/datadog/README.md                                  ← MODIFY (CI/CD 章追記)
docs/adr/0007-iac-cd-via-github-actions.md                   ← CREATE
docs/superpowers/specs/2026-05-26-datadog-slo-design.md      ← MODIFY (§8 Verification)
```

**触らないファイル**:

- `terraform/datadog/*.tf` (既存 monitors / dashboards / slos / rum / services / jira / slack / provider / variables / outputs) — backend 切替で動作は変わらない、コードは無変更
- `terraform/datadog/.gitignore` — `*.tfstate` 除外は維持 (state は HCP 側だが万一 local 操作が混ざってもコミットされない安全網として)
- `terraform/datadog/terraform.tfvars*` — 引き続き gitignored、HCP workspace に値を移すので不要

**前提**:

- 作業ブランチ: `016-datadog-docker-monitor-jira`
- 既存 SLO Block (commits `8af2abf..HEAD`) は merge 待ちまたは並行ブランチ。SLO Block 内で本 CI/CD plan を実装してもよい (workflow が動き出す前に SLO 6 リソースが commit されていれば、最初の apply で SLO も同時反映できて綺麗)
- Operator は spec §6 の手作業 (HCP セットアップ・state 移行) を **本 plan の Task 1-5 が commit された後・main merge 前**に実施する。順序が逆になるとローカル `terraform init` が壊れる

---

## Task 1: backend.tf 新規

**目的**: HCP Terraform backend を宣言。`<your-hcp-org>` は placeholder のまま commit (operator が後で置換)。本 task では terraform init / validate は走らせない (HCP workspace がまだ存在しないため)。

**Files:**

- Create: `terraform/datadog/backend.tf`

- [ ] **Step 1: ブランチ確認**

Run:

```bash
git branch --show-current
```

Expected: `016-datadog-docker-monitor-jira`

異なるブランチなら止めて人間に確認 (BLOCKED 報告)。

- [ ] **Step 2: backend.tf を作成**

Create `terraform/datadog/backend.tf`:

```hcl
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
```

- [ ] **Step 3: HCL syntax 検証 (init なし)**

`terraform validate` は HCP backend を要求し init が必要なので走らせられない。代わりに `terraform fmt -check` で HCL の構文と整形を確認。

Run:

```bash
cd terraform/datadog
terraform fmt -check backend.tf
```

Expected: exit 0 (出力なし)。non-zero なら `terraform fmt backend.tf` を実行して再 check。

- [ ] **Step 4: Commit**

```bash
cd /Users/kz/work/test-ai-app
git add terraform/datadog/backend.tf
git commit -m "$(cat <<'EOF'
infra(datadog): add HCP Terraform backend declaration

state を HCP Terraform free tier へ移管する準備。
<your-hcp-org> placeholder は operator が
README.md の手順に従って置換する。

spec: docs/superpowers/specs/2026-05-26-datadog-iac-cicd-design.md
EOF
)"
```

---

## Task 2: GitHub Actions workflow 新規

**目的**: PR で plan / main merge で apply する workflow を 1 ファイル / 2 job で作成。YAML 構文は Python の `yaml.safe_load` で事前検証。

**Files:**

- Create: `.github/workflows/terraform-datadog.yml`

- [ ] **Step 1: workflow ファイルを作成**

Create `.github/workflows/terraform-datadog.yml`:

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
  # ---- PR 時: plan を sticky comment で見せる ----
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

  # ---- main へ merge 後: apply ----
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

- [ ] **Step 2: YAML 構文を事前検証**

GitHub Actions 側でも syntactic 検査されるが、push 前に Python の `yaml.safe_load` で構文エラーを検出可能。

Run:

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/terraform-datadog.yml'))"
```

Expected: exit 0 (出力なし)。例外が出たら yaml の indent / quoting を直す。

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/terraform-datadog.yml
git commit -m "$(cat <<'EOF'
infra(ci): add terraform-datadog GH Actions workflow

PR open/push で plan を sticky comment、main merge で apply。
TF_API_TOKEN (GH secret) 1 つで HCP Terraform に認証。
Datadog credentials は HCP workspace env vars 側に格納。

paths filter: terraform/datadog/** + workflow 自身。
permissions: contents:read + pull-requests:write。
spec: docs/superpowers/specs/2026-05-26-datadog-iac-cicd-design.md
EOF
)"
```

---

## Task 3: README.md に CI/CD 章を追記

**目的**: `terraform/datadog/README.md` に CI/CD 章を追加し、operator 手順を documented runbook 化。既存「使い方」セクション (line 30 周辺) は手元 terraform apply 前提なので、CI/CD 移行後の文言に書き換えるか、両方並べる。今回は CI/CD 章を新規追加し、既存「使い方」は "ローカル開発用 (HCP 未移行時)" として残す方針。

**Files:**

- Modify: `terraform/datadog/README.md`

- [ ] **Step 1: 「含まれるリソース」セクションに CI/CD 項目を追加**

Edit `terraform/datadog/README.md`。直前 Block で追加された SLO bullet の **次の行** に以下を挿入:

```markdown
- **CI/CD** (`.github/workflows/terraform-datadog.yml`) — PR で `terraform plan` を sticky comment、main merge で `-auto-approve` apply。
  State は HCP Terraform。Datadog credentials も HCP workspace env vars 側。GH secret は `TF_API_TOKEN` 1 個のみ。
```

- [ ] **Step 2: 「使い方」セクションの見出しを「ローカル開発用」に書き換え**

Edit `terraform/datadog/README.md`。`## 使い方` の見出しの直下に以下の説明 1 行を挿入 (現在の bash コマンドブロックは残す):

```markdown
> CI/CD 移行後は手元 `terraform apply` は不要。下記は HCP 未移行時、または HCP を bypass してローカルで試したい場合の手順。
```

- [ ] **Step 3: 新規セクション「CI/CD (HCP Terraform + GitHub Actions)」を追加**

Edit `terraform/datadog/README.md`。`## State` セクション (line 49 周辺) の直前に以下のセクションを丸ごと挿入:

````markdown
## CI/CD (HCP Terraform + GitHub Actions)

### 起動条件

| トリガ                                                             | Job     | 動作                                            |
| ------------------------------------------------------------------ | ------- | ----------------------------------------------- |
| PR open / push (`terraform/datadog/**` または workflow 自身に変更) | `plan`  | `terraform plan` を実行し sticky comment に貼る |
| main へ merge (= push to main)                                     | `apply` | `terraform apply -auto-approve` を実行          |

PR レビュー時に sticky comment の plan 出力を必ず確認すること。auto-approve なので merge = apply 確定。

### Operator one-time セットアップ (CI が動き出す前に 1 回だけ)

1. **HCP Terraform サインアップ + workspace 作成** — `https://app.terraform.io/` で GitHub ログイン、Organization を作成 (例 `bz-kz`)、Workspace を CLI-driven mode で作成 (Name: `test-ai-app-datadog`、Terraform version 1.9.x)。
2. **Workspace variables 登録** (Variables タブ):
   - **Environment variables (Sensitive チェック必須)**: `DD_API_KEY`, `DD_APP_KEY`
   - **Terraform variables**: `env`, `app_name`, `owner_team`, `datadog_api_url`, `slack_account_name`, `slack_channels`, `monitor_recipients`, `jira_project_key` (現 `terraform.tfvars` から転記)
3. **User token 発行** — User Settings → Tokens → API tokens で発行。
4. **GH Actions secret 登録** — Repo Settings → Secrets and variables → Actions → New repository secret → Name: `TF_API_TOKEN`、Value: 上記 token。
5. **Placeholder 置換** — `<your-hcp-org>` を実 org 名に置換:
   ```bash
   sed -i '' 's/<your-hcp-org>/bz-kz/g' terraform/datadog/backend.tf .github/workflows/terraform-datadog.yml
   ```
````

(macOS の sed では `-i ''` が必要。Linux なら `-i` のみ) 6. **State 移行** — ローカル tfstate を HCP へ uploads:

```bash
cd terraform/datadog
set -a && source ../../.env && set +a
export TF_TOKEN_app_terraform_io="<TF_API_TOKEN>"
terraform init    # HCP migration prompt: "Do you want to copy existing state to HCP Terraform?" → yes
```

完了後、HCP workspace の "Resources" タブで既存リソース数 (16+) が表示されれば成功。7. **置換 + 移行をコミット + push** — backend.tf / workflow yml の置換結果と (もしあれば) `.terraform.lock.hcl` を 1 commit にまとめて push。PR を切ると plan job が動く (HCP backend を init するため TF_API_TOKEN を使用、ここで初通信)。8. **PR を merge** — apply job が走り、HCP workspace の state が "no changes" であることを確認 (state 移行ですでに反映済の場合)。

### トラブルシュート

| 症状                                                                                   | 確認                                                                                                                                                                           |
| -------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| plan job が `Error: No valid credential sources` で落ちる                              | `TF_API_TOKEN` secret が repo 設定にあるか、HCP token が失効していないか                                                                                                       |
| apply job が `Error: 401 Unauthorized` (Datadog API)                                   | HCP workspace の `DD_API_KEY` / `DD_APP_KEY` env vars に Sensitive チェック + 値 が入っているか、`Category: Environment variable` (Terraform variable ではない) になっているか |
| plan の sticky comment が空                                                            | `plan` step が早期に失敗している。Actions log で `terraform fmt -check` / `terraform init` / `terraform validate` のどこで止まったか確認                                       |
| apply 後も pre-existing drift 2 件 (`overview` / `error_log_spike`) が plan に出続ける | 想定通り、本 Block では解消しない (別 Block 候補)。UI を tf に揃えるか、tf を UI に揃えるか別途判断                                                                            |

````

- [ ] **Step 4: 差分確認**

Run:
```bash
git diff terraform/datadog/README.md
````

Expected: 上記 3 ブロックの追加のみ。他の行の予期せぬ変更が無いこと。

- [ ] **Step 5: Commit**

```bash
git add terraform/datadog/README.md
git commit -m "$(cat <<'EOF'
docs(datadog): document CI/CD layer + operator one-time setup

HCP Terraform セットアップ・GH secret 登録・placeholder 置換・
state 移行の 6 step を runbook 化。トラブルシュート 4 件併記。
既存「使い方」は HCP 未移行時のローカル開発用に位置付け直し。
EOF
)"
```

---

## Task 4: ADR-0007 新規

**目的**: 「Datadog Terraform に限り CI/CD で apply する、Datadog 以外は明示 opt-in 要」という方針を ADR として固定。`CLAUDE.md` §2 (Local-only PoC) の方針境界変更にあたるため必須。

**Files:**

- Create: `docs/adr/0007-iac-cd-via-github-actions.md`

- [ ] **Step 1: 既存 ADR の構造を確認**

Run:

```bash
cat docs/adr/0000-template.md
```

セクション順: Status / Date / Owner / Related Spec → Context → Decision → Consequences → Alternatives considered → Gates affected → Open follow-ups。

- [ ] **Step 2: ADR-0007 を作成**

Create `docs/adr/0007-iac-cd-via-github-actions.md`:

```markdown
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
  - State 移行 (HCP の interactive プロンプト経由の `terraform init`) は逆方向の運用が手間 (HCP → local) なので、HCP からの離脱はコスト中。
  - HCP workspace variables の管理が Terraform 外 (HCP UI の手動) に逃げる「鶏卵」が発生する。
- **Reversibility:**
  - **Moderate**。HCP workspace の state を `terraform state pull` でローカルへ取り出し、`backend.tf` を削除して `terraform init` (interactive プロンプトで yes) で local backend へ戻すことは技術的には可能。ただし HCP workspace variables の手動退避が必要。

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
```

- [ ] **Step 3: Commit**

```bash
git add docs/adr/0007-iac-cd-via-github-actions.md
git commit -m "$(cat <<'EOF'
docs(adr): 0007 — datadog terraform CI/CD via GH Actions

CLAUDE.md §2「Local-only PoC」の境界を Datadog terraform に限り
拡張する判断。HCP Terraform backend + auto-approve apply on merge。
他 terraform は明示 opt-in 要 (本 ADR の境界条件)。

related spec: docs/superpowers/specs/2026-05-26-datadog-iac-cicd-design.md
EOF
)"
```

---

## Task 5: 既存 SLO spec §8 Verification を CI 前提に書き換え

**目的**: `docs/superpowers/specs/2026-05-26-datadog-slo-design.md` §8 の Verification セクションは現在手元 `terraform apply` 前提。CI/CD 移行後は merge = apply なので、Block 完了後の確認手順を CI 前提に書き換える。

**Files:**

- Modify: `docs/superpowers/specs/2026-05-26-datadog-slo-design.md`

- [ ] **Step 1: 該当箇所の現状を確認**

Run:

```bash
grep -n '^## 8\.' docs/superpowers/specs/2026-05-26-datadog-slo-design.md
```

`## 8. 適用後 verification` の行番号を控える。

- [ ] **Step 2: §8 を書き換え**

Edit `docs/superpowers/specs/2026-05-26-datadog-slo-design.md`。`## 8. 適用後 verification` セクション全体 (`## 9. ADR の要否` 直前まで) を以下に置換:

```markdown
## 8. 適用後 verification

ADR-0007 (CI/CD via GH Actions) 採択後は **PR merge = terraform apply 完了**。Block 完了後の確認手順:

1. **PR 上で sticky comment plan を確認** — `Plan: 6 to add, 2 to change, 0 to destroy` (= SLO 6 + pre-existing drift 2) であること。それ以上の resource が変更対象に出ていたら止まる。
2. **PR merge** — auto-merge は禁止、人間が手で merge ボタンを押す。
3. **GH Actions の `apply` job が緑** — Actions タブで terraform-datadog workflow の最新 run が success。
4. **HCP Terraform Runs ページ** — 該当 run が `applied` ステータス、`6 added, 2 changed` の表示。
5. **Datadog UI** で:
   - Service Reliability → SLO list に 3 件 (`backend availability` / `LLM /generate p95 < 7min` / `frontend LCP < 2500ms`) が並ぶ。
   - Monitors → SLO Alerts に 3 件 (`SLO breach — *`)。
   - 初期 status は "No data" / "Calculating" (Caveat C3)。

### Smoke (denominator にデータを 1 つ落とす)

CI apply 完了後、ローカルから:

1. `docker compose up -d`
2. ブラウザで `http://localhost:3000/` → frontend RUM view event 1 件
3. `curl http://localhost:8000/health` → backend `trace.hits` 1 件
4. UI で `/api/generate` を 1 回呼ぶ → LLM latency 1 サンプル

### Metrics Explorer 確認

Datadog UI → Metrics Explorer で以下が 1 点でも見えれば配線 OK:

- `trace.backend.request.hits{env:local}`
- `p95:trace.backend.request{resource_name:POST_/api/generate,env:local}`
- `@view.largest_contentful_paint{service:frontend-browser,env:local}` (RUM Analytics 側)

LCP の custom metric (`rum.lcp.good` / `rum.lcp.total`) は未生成のため出ない (D2 で別 Block 対応)。
```

- [ ] **Step 3: 差分確認**

Run:

```bash
git diff docs/superpowers/specs/2026-05-26-datadog-slo-design.md
```

Expected: §8 セクション全体の置換のみ。他のセクション (§7、§9 以降) に変更が無いこと。

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-05-26-datadog-slo-design.md
git commit -m "$(cat <<'EOF'
docs(slo): rewrite §8 verification for CI/CD apply flow

ADR-0007 採択により Block 完了後は PR merge = apply に変わる。
sticky comment plan の確認 / HCP Runs / Datadog UI / smoke の
4 段確認に書き換え。手元 terraform apply 手順は削除。
EOF
)"
```

---

## Task 6: Operator handoff (agent 不実行)

**目的**: CI/CD を実際に動かすために operator が手で行うべきステップを runbook 化し、agent はここで止まる。Task 1-5 の commit が main に landing する前に、operator は以下を完了させる。

> **重要**: このタスクは外部状態 (HCP Terraform organization、GH Actions secret、ローカル `terraform init` での state 移行) を変更します。エージェントが自動実行せず、**人間オペレータが手動で実行** してください。

- [ ] **Step 1: HCP Terraform セットアップ**

`terraform/datadog/README.md` の "CI/CD" 章 "Operator one-time セットアップ" 1〜4 を順に実施。

具体的には:

1. `https://app.terraform.io/` でサインアップ (GitHub ログイン可)
2. Organization 作成 (例 `bz-kz`)
3. Workspace `test-ai-app-datadog` を CLI-driven workflow mode で作成、Terraform version 1.9.x
4. Workspace → Variables で以下を登録:
   - Environment variables (Sensitive チェック): `DD_API_KEY`, `DD_APP_KEY`
   - Terraform variables (現 `terraform.tfvars` から転記): `env`, `app_name`, `owner_team`, `datadog_api_url`, `slack_account_name`, `slack_channels`, `monitor_recipients`, `jira_project_key`
5. User Settings → Tokens で API token を発行 (この値は再表示不可、保管)

- [ ] **Step 2: GH Actions secret 登録**

GitHub repo の Settings → Secrets and variables → Actions → New repository secret:

- Name: `TF_API_TOKEN`
- Value: Step 1-5 で発行した HCP token

- [ ] **Step 3: Placeholder 置換**

`<your-hcp-org>` を実 org 名に置換:

```bash
cd /Users/kz/work/test-ai-app
# 例: org 名が "bz-kz" の場合
sed -i '' 's/<your-hcp-org>/bz-kz/g' terraform/datadog/backend.tf .github/workflows/terraform-datadog.yml
```

(Linux なら `-i ''` を `-i` に)

確認:

```bash
grep -n '<your-hcp-org>' terraform/datadog/backend.tf .github/workflows/terraform-datadog.yml
```

Expected: 出力なし (置換完了)。

- [ ] **Step 4: ローカル state 移行**

```bash
cd terraform/datadog
set -a && source ../../.env && set +a
export TF_TOKEN_app_terraform_io="<HCP_API_TOKEN_FROM_STEP_1>"
terraform init
# HCP migration: "Do you want to copy existing state to HCP Terraform?" に yes
# (注: -migrate-state flag は HCP backend では使えない。flag 無しの terraform init が interactive prompt を出す)
```

完了確認: HCP workspace の "Resources" タブで既存 16 リソースが表示。

- [ ] **Step 5: 置換結果を commit**

```bash
cd /Users/kz/work/test-ai-app
git add terraform/datadog/backend.tf .github/workflows/terraform-datadog.yml
# .terraform.lock.hcl が生成 / 更新されていれば一緒に追加
[ -f terraform/datadog/.terraform.lock.hcl ] && git add terraform/datadog/.terraform.lock.hcl

git commit -m "$(cat <<'EOF'
infra(datadog): operator-side placeholder substitution + lock file

<your-hcp-org> を実 org 名に置換し、HCP backend init で生成された
.terraform.lock.hcl を commit。state 移行は完了 (HCP workspace
test-ai-app-datadog に 16+ resources 登録)。
EOF
)"
```

- [ ] **Step 6: PR を切る (まだなければ)**

```bash
git push origin 016-datadog-docker-monitor-jira
gh pr create --base main --head 016-datadog-docker-monitor-jira \
  --title "feat(datadog): SLO monitoring + CI/CD via GH Actions" \
  --body-file <(cat <<'EOF'
## Summary
- 3 SLO + 3 SLO alert monitor (backend availability / LLM latency / frontend LCP) を `terraform/datadog/slos.tf` に追加
- `terraform/datadog/` の state を HCP Terraform へ移管、PR で plan / main merge で apply の CI/CD を `.github/workflows/terraform-datadog.yml` に追加
- ADR-0007 で Datadog だけ CI/CD 化する境界を明記

## Test plan
- [x] `terraform fmt -check -recursive` 緑
- [x] PR の sticky comment plan が "6 to add, 2 to change" (SLO 6 + pre-existing drift 2) を表示
- [ ] merge 後、GH Actions apply job が success
- [ ] HCP Terraform Runs ページで該当 run が `applied`
- [ ] Datadog UI Service Reliability → SLO list に 3 件
- [ ] Datadog UI Monitors → SLO Alerts に 3 件

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)
```

PR open 直後に `terraform-datadog` workflow の `plan` job が起動する。Actions タブで状態確認。

- [ ] **Step 7: PR レビュー + merge**

PR の sticky comment plan を確認:

- 期待: `Plan: 6 to add, 2 to change, 0 to destroy.`
- 想定外 (= "to destroy" あり、または add 数が違う) なら merge せず原因調査

問題なければ merge ボタンを押す (auto-merge は禁止、ADR-0005 + 0007 とも整合)。Merge により `apply` job が main 上で起動。

- [ ] **Step 8: Apply 完了確認**

- GH Actions の `terraform-datadog` workflow 最新 run (event = push) が success
- HCP Terraform Runs ページで該当 run が `applied`、`6 added, 2 changed`
- Datadog UI Service Reliability → SLO list に 3 件、Monitors → SLO Alerts に 3 件

これで Block 完了。

---

## Self-Review

**1. Spec coverage**:

| Spec section                     | Task                                            |
| -------------------------------- | ----------------------------------------------- |
| §3 アーキテクチャ                | Task 1 (backend) + Task 2 (workflow) で具現化   |
| §4 Workflow ファイル             | Task 2                                          |
| §5 Backend 切替                  | Task 1                                          |
| §6.1 HCP セットアップ (operator) | Task 6 Step 1                                   |
| §6.2 Placeholder 置換 (operator) | Task 6 Step 3                                   |
| §6.3 State 移行 (operator)       | Task 6 Step 4                                   |
| §6.4 検証                        | Task 6 Step 4 末尾 + Task 6 Step 8              |
| §7 ADR-0007                      | Task 4                                          |
| §8 障害モード                    | Task 3 (README troubleshoot 表) で覆う          |
| §9 Provider auth 検証ポイント    | Task 6 Step 1-4 (Sensitive チェック + Category) |
| §10 Rollback                     | 本 plan では実施しない (運用 doc は README)     |
| §11 Caveats                      | Task 3 README + Task 4 ADR Consequences で記述  |
| §12 Deferred items               | Task 4 ADR Open follow-ups                      |
| §13 Block scope                  | 全 Task に分散                                  |

ギャップなし。

**2. Placeholder scan**:

- TBD / TODO は本 plan 内に無し。
- `<your-hcp-org>` は code 内の意図的 placeholder で、Task 6 Step 3 で operator が置換する手順を明示してある。
- `<HCP_API_TOKEN_FROM_STEP_1>` は Task 6 Step 4 内の operator が手で埋めるべき token、説明済。

**3. Type consistency**:

- Workspace 名 `test-ai-app-datadog` は Task 1 (backend.tf) と Task 2 (workflow env `TF_WORKSPACE`) と Task 3 README と Task 6 操作で同一。
- Secret 名 `TF_API_TOKEN` は Task 2 workflow と Task 3 README と Task 6 で同一。
- Env var name `TF_TOKEN_app_terraform_io` は Task 3 README と Task 6 で同一。
- 認証 path: GH secret → workflow env → CLI auth、と Datadog credentials は HCP workspace env → terraform process env → provider auto-detect、の 2 経路明記。

問題なし。

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-26-datadog-iac-cicd.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
