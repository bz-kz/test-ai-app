# Datadog SLO Monitoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `terraform/datadog/` に `slos.tf` を追加し、3 つの SLO (backend availability / LLM /generate latency / frontend LCP) と対応する SLO alert monitor を IaC で管理する。

**Architecture:** Datadog Terraform provider の `datadog_service_level_objective` リソースを 3 本立て、それぞれに `datadog_monitor` (`type = "slo alert"`) を 1 本ずつ紐づける。既存 monitors.tf の `local.recipient_block` / `local.jira_block` を流用して通知を一元化。LLM latency のみ event-count では実装困難なため `type = "time_slice"` を採用。

**Tech Stack:** Terraform ≥ 1.7, DataDog/datadog provider 3.50+, HCL only (新規ランタイムコード変更なし).

**Spec:** [`docs/superpowers/specs/2026-05-26-datadog-slo-design.md`](../specs/2026-05-26-datadog-slo-design.md)

---

## File Structure

```
terraform/datadog/
├── slos.tf            ← CREATE (新規)
└── README.md          ← MODIFY (SLO 章を追記)
```

**触らないファイル**:

- `monitors.tf` — 既存 monitor は維持。SLO は別レイヤとして並存
- `outputs.tf` — SLO ID を `.env` に転記する用途は無いので output 不要
- `terraform.tfvars` — 新 var 不要 (既存 `var.app_name` / `var.env` で足りる)

**前提**:

- 作業ブランチ: `016-datadog-docker-monitor-jira` (PR を立てるのはこのブランチで)
- 既に `terraform init` 済み (`terraform/datadog/.terraform/` あり)
- `.env` に `DD_API_KEY` / `DD_APP_KEY` 設定済み

---

## Task 1: slos.tf スキャフォールド + validate

**目的**: 空の slos.tf を作って `terraform validate` / `terraform plan` がクリーンに通ることを確認 (= 既存 state を壊していない baseline)。

**Files:**

- Create: `terraform/datadog/slos.tf`

- [ ] **Step 1: ブランチ確認**

Run:

```bash
git branch --show-current
```

Expected: `016-datadog-docker-monitor-jira`

このブランチでなければ作業を中止して人間に確認。

- [ ] **Step 2: slos.tf を作成 (file header のみ、resource はまだ無し)**

Create `terraform/datadog/slos.tf`:

```hcl
# Datadog SLO 定義。設計の根拠は docs/superpowers/specs/2026-05-26-datadog-slo-design.md。
#
# 3 SLO + 3 SLO alert monitor:
# - backend_availability (metric-based)         + slo_alert_backend_availability
# - llm_latency          (time-slice)           + slo_alert_llm_latency
# - frontend_lcp         (metric-based, RUM)    + slo_alert_frontend_lcp
#
# 通知は monitors.tf の local.recipient_block + local.jira_block を流用。
# SLO threshold には warning 行を付けない (1-tier breach 方針、設計 §5)。
```

- [ ] **Step 3: terraform fmt + validate**

Run:

```bash
cd terraform/datadog
terraform fmt -check slos.tf
terraform validate
```

Expected: 両方 exit 0。validate は `Success! The configuration is valid.`

- [ ] **Step 4: terraform plan で no-op 確認**

Run:

```bash
set -a && source ../../.env && set +a
terraform plan -out=/tmp/slo-task1.plan
```

Expected: `No changes. Your infrastructure matches the configuration.`

(コメントだけのファイルなのでリソース差分が出ないこと)

- [ ] **Step 5: Commit**

```bash
cd ../..
git add terraform/datadog/slos.tf
git commit -m "$(cat <<'EOF'
infra(datadog): scaffold slos.tf

3 SLO + 3 alert monitor の追加先ファイルを用意 (中身は次タスク以降)。
spec: docs/superpowers/specs/2026-05-26-datadog-slo-design.md
EOF
)"
```

---

## Task 2: Backend availability SLO + alert monitor

**目的**: 1 つ目の SLO (metric-based event ratio) と対応する alert を追加。Apply はまだ行わない (plan で差分を確認するのみ)。

**Files:**

- Modify: `terraform/datadog/slos.tf` (Task 1 で作成済)

- [ ] **Step 1: SLO リソースを slos.tf に追記**

Append to `terraform/datadog/slos.tf`:

```hcl

# ----------------------------------------------------------------------------
# SLO: Backend availability (5xx 以外の success rate ≥ 99% / 7d)
# ----------------------------------------------------------------------------
# query は既存 backend_5xx_rate monitor と同じ trace metric を使用。
# trace metric が流れ始めるまでは "No data" のままだが apply は通る。
resource "datadog_service_level_objective" "backend_availability" {
  name        = "[${var.app_name}] backend availability 7d"
  type        = "metric"
  description = "Backend HTTP の success rate (5xx 以外) を 7d rolling で計測。既存 backend_5xx_rate monitor の SLI 版。"

  query {
    numerator   = "sum:trace.backend.request.hits{service:backend,env:${var.env}}.as_count() - sum:trace.backend.request.errors{service:backend,env:${var.env}}.as_count()"
    denominator = "sum:trace.backend.request.hits{service:backend,env:${var.env}}.as_count()"
  }

  thresholds {
    timeframe = "7d"
    target    = 99.0
  }

  tags = concat(local.common_tags, ["category:slo", "sli:backend_availability"])
}
```

- [ ] **Step 2: SLO alert monitor を追記**

Append to `terraform/datadog/slos.tf`:

```hcl

# ----------------------------------------------------------------------------
# Alert: backend_availability SLO breach
# ----------------------------------------------------------------------------
resource "datadog_monitor" "slo_alert_backend_availability" {
  name    = "[${var.app_name}] SLO breach — backend availability"
  type    = "slo alert"
  message = <<-EOT
    Backend availability SLO (7d, target 99%) が割れました。
    5xx が長期的に増えている可能性 — 既存 monitor backend_5xx_rate と logs を見て原因を探してください。
    ${local.recipient_block}
    ${local.jira_block}
  EOT

  query = "error_budget(\"${datadog_service_level_objective.backend_availability.id}\").over(\"7d\") > 100"

  monitor_thresholds {
    critical = 100
  }

  notify_no_data = false

  tags = concat(local.common_tags, ["category:slo-alert", "sli:backend_availability"])
}
```

- [ ] **Step 3: fmt + validate**

Run:

```bash
cd terraform/datadog
terraform fmt -check slos.tf
terraform validate
```

Expected: 両方クリーン。validate が schema エラーを返したら `error_budget(...)` の構文や `query`/`thresholds` ブロックを Datadog provider docs で確認して修正。

- [ ] **Step 4: terraform plan で差分が 2 件 add であることを確認**

Run:

```bash
set -a && source ../../.env && set +a
terraform plan -out=/tmp/slo-task2.plan | tail -20
```

Expected の末尾:

```
Plan: 2 to add, 0 to change, 0 to destroy.
```

2 件 = `datadog_service_level_objective.backend_availability` + `datadog_monitor.slo_alert_backend_availability`

3 件以上出たら他のリソースに想定外の変更が混じっているので止まって調査。

- [ ] **Step 5: Commit**

```bash
cd ../..
git add terraform/datadog/slos.tf
git commit -m "$(cat <<'EOF'
infra(datadog): add backend availability SLO + alert monitor

7d rolling, target 99%。既存 backend_5xx_rate monitor と同じ
trace metric を SLI として再利用。alert は 100% breach のみ
(burn rate 無し、設計 §5)。
EOF
)"
```

---

## Task 3: LLM /generate latency SLO (time-slice) + alert monitor

**目的**: 2 つ目の SLO。Time-slice 型で「p95 < 7min となっている時間の割合」を測る。

**Files:**

- Modify: `terraform/datadog/slos.tf`

- [ ] **Step 1: Time-slice SLO リソースを追記**

Append to `terraform/datadog/slos.tf`:

```hcl

# ----------------------------------------------------------------------------
# SLO: LLM /generate p95 latency < 7 分 (time-slice)
# ----------------------------------------------------------------------------
# Approach A (metric-based event-count) は APM Span-Based Metric が必要で
# IaC 完結を崩すため、ここだけ time_slice 型を採用。設計 §4.2 / Caveat C1。
# INF-006: CPU 推論の通常 p95 = 4-5 分 (~300s)、+50% で alert に揃える。
resource "datadog_service_level_objective" "llm_latency" {
  name        = "[${var.app_name}] LLM /generate p95 < 7min 7d"
  type        = "time_slice"
  description = "LLM 推論 p95 latency が 7 分 (420s) 未満である time slice の割合。INF-006: CPU 推論の通常 p95 = 4-5 分。"

  sli_specification {
    time_slice {
      query {
        formula {
          formula_expression = "query1"
        }
        query {
          metric_query {
            name  = "query1"
            query = "p95:trace.backend.request{service:backend,env:${var.env},resource_name:POST_/api/generate}"
          }
        }
      }
      comparator = "<"
      threshold  = 420000 # ms
    }
  }

  thresholds {
    timeframe = "7d"
    target    = 95.0
  }

  tags = concat(local.common_tags, ["category:slo", "sli:llm_latency", "subsystem:llm"])
}
```

- [ ] **Step 2: SLO alert monitor を追記**

Append to `terraform/datadog/slos.tf`:

```hcl

# ----------------------------------------------------------------------------
# Alert: llm_latency SLO breach
# ----------------------------------------------------------------------------
resource "datadog_monitor" "slo_alert_llm_latency" {
  name    = "[${var.app_name}] SLO breach — LLM /generate latency"
  type    = "slo alert"
  message = <<-EOT
    LLM /generate latency SLO (7d, p95 < 7min target 95%) が割れました。
    確認: 既存 monitor llm_latency_p95 / llm_container_memory、ホスト CPU 占有、Ollama keep_alive。
    ${local.recipient_block}
    ${local.jira_block}
  EOT

  query = "error_budget(\"${datadog_service_level_objective.llm_latency.id}\").over(\"7d\") > 100"

  monitor_thresholds {
    critical = 100
  }

  notify_no_data = false

  tags = concat(local.common_tags, ["category:slo-alert", "sli:llm_latency", "subsystem:llm"])
}
```

- [ ] **Step 3: fmt + validate**

Run:

```bash
cd terraform/datadog
terraform fmt -check slos.tf
terraform validate
```

Expected: 両方クリーン。`sli_specification` ブロックの schema エラーが出たら provider バージョンが古い可能性 — `versions.tf` (or `provider.tf`) で `DataDog/datadog` が 3.50+ を要求しているか確認。

- [ ] **Step 4: terraform plan で差分が 4 件 add (累計) であることを確認**

Run:

```bash
set -a && source ../../.env && set +a
terraform plan -out=/tmp/slo-task3.plan | tail -20
```

Expected: `Plan: 4 to add, 0 to change, 0 to destroy.` (Task 2 の 2 件 + 今回の 2 件)

- [ ] **Step 5: Commit**

```bash
cd ../..
git add terraform/datadog/slos.tf
git commit -m "$(cat <<'EOF'
infra(datadog): add LLM /generate latency SLO (time-slice) + alert

7d rolling, target 95% (= p95 < 7min を 7d 中 95% 維持)。
event-count 統一は APM Span-Based Metric が必要なため deferred、
time-slice 型でひとまず IaC 完結 (設計 §4.2 / Caveat C1 / D1)。
EOF
)"
```

---

## Task 4: Frontend LCP SLO + alert monitor (placeholder metric)

**目的**: 3 つ目の SLO。RUM-derived custom metric (`rum.lcp.good` / `rum.lcp.total`) を numerator/denominator にする前提。当面 metric が未生成のため SLO は "No data" のままだが、IaC として apply は通る。

**Files:**

- Modify: `terraform/datadog/slos.tf`

- [ ] **Step 1: SLO リソースを追記**

Append to `terraform/datadog/slos.tf`:

```hcl

# ----------------------------------------------------------------------------
# SLO: Frontend LCP < 2500ms (Google Core Web Vital "Good")
# ----------------------------------------------------------------------------
# numerator/denominator の metric (rum.lcp.good / rum.lcp.total) は本 Block
# 時点では Datadog 側に存在しない custom metric。RUM Analytics の
# Generate Metric を別 Block (deferred D2) で作るまで SLO は "No data"。
# IaC としては apply 可能 (Datadog はエラーにせず No data 扱い)。
resource "datadog_service_level_objective" "frontend_lcp" {
  name        = "[${var.app_name}] frontend LCP < 2500ms 7d"
  type        = "metric"
  description = "Frontend RUM view event のうち LCP < 2500ms の割合。Google Core Web Vital「Good」(p75 < 2500ms) に準拠。custom metric の生成は deferred (D2)。"

  query {
    numerator   = "sum:rum.lcp.good{service:frontend-browser,env:${var.env}}.as_count()"
    denominator = "sum:rum.lcp.total{service:frontend-browser,env:${var.env}}.as_count()"
  }

  thresholds {
    timeframe = "7d"
    target    = 75.0
  }

  tags = concat(local.common_tags, ["category:slo", "sli:frontend_lcp", "service:frontend-browser"])
}
```

- [ ] **Step 2: SLO alert monitor を追記**

Append to `terraform/datadog/slos.tf`:

```hcl

# ----------------------------------------------------------------------------
# Alert: frontend_lcp SLO breach
# ----------------------------------------------------------------------------
resource "datadog_monitor" "slo_alert_frontend_lcp" {
  name    = "[${var.app_name}] SLO breach — frontend LCP"
  type    = "slo alert"
  message = <<-EOT
    Frontend LCP SLO (7d, target 75% of view events < 2500ms) が割れました。
    確認: RUM Performance dashboard、最近の frontend deploy、画像/フォント遅延、サードパーティ script。
    ${local.recipient_block}
    ${local.jira_block}
  EOT

  query = "error_budget(\"${datadog_service_level_objective.frontend_lcp.id}\").over(\"7d\") > 100"

  monitor_thresholds {
    critical = 100
  }

  notify_no_data = false

  tags = concat(local.common_tags, ["category:slo-alert", "sli:frontend_lcp", "service:frontend-browser"])
}
```

- [ ] **Step 3: fmt + validate**

Run:

```bash
cd terraform/datadog
terraform fmt -check slos.tf
terraform validate
```

Expected: 両方クリーン。

- [ ] **Step 4: terraform plan で差分が 6 件 add (累計) であることを確認**

Run:

```bash
set -a && source ../../.env && set +a
terraform plan -out=/tmp/slo-task4.plan | tail -20
```

Expected: `Plan: 6 to add, 0 to change, 0 to destroy.`

- [ ] **Step 5: Commit**

```bash
cd ../..
git add terraform/datadog/slos.tf
git commit -m "$(cat <<'EOF'
infra(datadog): add frontend LCP SLO + alert (placeholder metric)

7d rolling, target 75% (Core Web Vitals Good 準拠)。
numerator/denominator の rum.lcp.good / rum.lcp.total は
RUM Generate Metric で別 Block 生成 (deferred D2)。SLO 本体は
apply 可、custom metric 生成まで "No data" 表示。
EOF
)"
```

---

## Task 5: README.md に SLO 章を追記

**目的**: `terraform/datadog/README.md` の「含まれるリソース」「既知の調整ポイント」を更新し、新しい SLO レイヤを文書化。

**Files:**

- Modify: `terraform/datadog/README.md`

- [ ] **Step 1: 「含まれるリソース」セクションに SLO 項目を追加**

Edit `terraform/datadog/README.md`。`- **Dashboard** (...)` 行の **次の行** に以下を挿入:

```markdown
- **SLO** (`slos.tf`) — 3 SLO + 3 SLO alert monitor。7d rolling、target は
  backend availability 99% / LLM /generate p95 < 7min 95% / frontend LCP < 2500ms 75%。
  通知は monitors.tf と同じ Slack/Jira pipeline を流用。設計詳細は
  `docs/superpowers/specs/2026-05-26-datadog-slo-design.md`。
```

- [ ] **Step 2: 「既知の調整ポイント」セクションに SLO の caveat を追加**

Edit `terraform/datadog/README.md`。「既知の調整ポイント」の `- Monitor 閾値は仮置き。...` の **次の行** に以下を挿入:

```markdown
- 新規 SLO は最初の 7d は "No data" / "Calculating" 表示が正常。Service Reliability
  ページで 7d 経過後に本値が出る。
- `frontend_lcp` SLO は `rum.lcp.good` / `rum.lcp.total` custom metric に依存。
  これらは RUM Analytics の Generate Metric で別 Block 作成 (spec D2)。
  未生成のうちは LCP SLO のみ恒久 "No data"。他 2 SLO は影響なし。
- LLM latency SLO は time-slice 型。event-count への統一は APM Span-Based Metric
  追加が必要 (spec D1) で deferred。
```

- [ ] **Step 3: 差分確認**

Run:

```bash
git diff terraform/datadog/README.md
```

Expected: 上記 2 ブロックの追加のみ (他の行に予期せぬ変更が無いこと)。

- [ ] **Step 4: Commit**

```bash
git add terraform/datadog/README.md
git commit -m "$(cat <<'EOF'
docs(datadog): document SLO layer in terraform/datadog README

slos.tf の追加と "No data" 初期挙動、LCP custom metric 依存、
LLM time-slice 採用の caveat を runbook 化。
EOF
)"
```

---

## Task 6: terraform apply + smoke verification (operator-driven)

**目的**: 実 Datadog org に 6 リソースを apply し、UI 上で配線確認 + smoke 操作で初期 data を 1 件ずつ流す。

> **重要**: このタスクは外部状態 (実 Datadog org) を変更します。エージェントが自動実行せず、**人間オペレータが手動で実行** してください。コマンド出力をエージェントに渡せば後続の検証は手伝えます。

- [ ] **Step 1: 最終 plan を確認**

Run:

```bash
cd terraform/datadog
set -a && source ../../.env && set +a
terraform plan -out=/tmp/slo-final.plan
```

Expected: `Plan: 6 to add, 0 to change, 0 to destroy.`

差分の内訳:

- `datadog_service_level_objective.backend_availability` (add)
- `datadog_service_level_objective.frontend_lcp` (add)
- `datadog_service_level_objective.llm_latency` (add)
- `datadog_monitor.slo_alert_backend_availability` (add)
- `datadog_monitor.slo_alert_frontend_lcp` (add)
- `datadog_monitor.slo_alert_llm_latency` (add)

それ以外の resource に変更が出ていたら止まって調査 (drift)。

- [ ] **Step 2: Apply**

Run:

```bash
terraform apply /tmp/slo-final.plan
```

Expected: `Apply complete! Resources: 6 added, 0 changed, 0 destroyed.`

- [ ] **Step 3: Datadog UI 上で SLO list を確認**

ブラウザで Datadog → **Service Mgmt → SLOs** を開き、以下 3 件が並ぶこと:

- `[<app_name>] backend availability 7d`
- `[<app_name>] LLM /generate p95 < 7min 7d`
- `[<app_name>] frontend LCP < 2500ms 7d`

初期 status は **"No data" / "Calculating"** が正常 (7d 分蓄積まで本値出ない)。

- [ ] **Step 4: SLO alert monitor が立っていることを確認**

Datadog → **Monitors → Manage Monitors**、`type:"slo alert"` でフィルタ。以下 3 件:

- `[<app_name>] SLO breach — backend availability`
- `[<app_name>] SLO breach — LLM /generate latency`
- `[<app_name>] SLO breach — frontend LCP`

各 monitor の status は **"No Data"** が正常。

- [ ] **Step 5: Smoke 操作で denominator にデータを 1 件ずつ落とす**

```bash
# Compose を起動
docker compose up -d

# Backend hit (1 件): trace.backend.request.hits の denominator が +1
curl -s http://localhost:8000/health

# Frontend view event (1 件): rum.lcp.* (= LCP custom metric は未生成だが view event 自体は流れる)
# ブラウザで http://localhost:3000/ を 1 回開く

# LLM /generate (1 件): p95 計算の母集団 +1
# UI で 1 回録音→草案生成、または curl で /api/generate を 1 回叩く
```

- [ ] **Step 6: Metrics Explorer で metric 流入を確認**

Datadog → **Metrics → Explorer** で以下を順に query:

| Metric                                                                               | Expected                             |
| ------------------------------------------------------------------------------------ | ------------------------------------ |
| `sum:trace.backend.request.hits{env:local}.as_count()`                               | 1 以上の data point                  |
| `p95:trace.backend.request{resource_name:POST_/api/generate,env:local}`              | data point あり (推論を実行した場合) |
| `@view.largest_contentful_paint{service:frontend-browser,env:local}` (RUM Analytics) | view event 1 件以上                  |

LCP の custom metric (`rum.lcp.good` / `rum.lcp.total`) は **未生成のため出てこなくて正常**。

- [ ] **Step 7: PR 作成 (任意、ブランチ運用ポリシー次第)**

このブランチ全体を main にマージしたいタイミングで、`AGENTS.md` §8.7 と `.claude/skills/git-pr-flow/SKILL.md` の手順に従って PR を起票。本 plan の 5 commit はそのまま PR に含まれる。

(エージェントは push まで、merge は人間が実行)

---

## Self-Review

**1. Spec coverage**:

| Spec section                  | Task                                      |
| ----------------------------- | ----------------------------------------- |
| §3 ファイル配置               | Task 1 (scaffold), Task 5 (README)        |
| §4.1 backend_availability     | Task 2                                    |
| §4.2 llm_latency (time-slice) | Task 3                                    |
| §4.3 frontend_lcp             | Task 4                                    |
| §5 通知配線 (3 alert monitor) | Task 2-4 のそれぞれに含む                 |
| §6 Caveats (C1-C5)            | Task 3 / Task 4 / Task 5 README で記述    |
| §7 Deferred items             | 本 plan 範囲外 (明示的に deferred と記述) |
| §8 Verification               | Task 6                                    |
| §9 ADR 不要                   | 本 plan で ADR 触らず ✓                   |

ギャップなし。

**2. Placeholder scan**: TBD / TODO / "implement later" 該当なし。すべての code block は実コード。

**3. Type consistency**:

- SLO resource 名 (`backend_availability` / `llm_latency` / `frontend_lcp`) は Task 2-4 で一貫
- Alert monitor 名 (`slo_alert_<sli>`) も一貫
- `error_budget("<id>").over("7d") > 100` パターンは 3 alert で同じ

問題なし。

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-26-datadog-slo-monitoring.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
