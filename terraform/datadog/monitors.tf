# Monitor 定義。query は trace metric が Datadog に流れ始めてから実値に合わせて調整。
# 通知先 (@-handle) は var.monitor_recipients。空のままだと通知無し (定義のみ)。
#
# 各 monitor の閾値は仮置き。実運用は最初の 1 週間でベースライン取って tighten する。

locals {
  # var.slack_channels から Datadog Slack @-handle を自動生成
  # 例: #all-datadog-notify → @slack-datadognotify-all-datadog-notify
  slack_handles = [
    for ch in var.slack_channels :
    "@slack-${var.slack_account_name}-${trimprefix(ch, "#")}"
  ]

  # Slack + 手動指定 (email/PagerDuty 等) をマージして monitor message に埋め込む
  all_recipients  = concat(local.slack_handles, var.monitor_recipients)
  recipient_block = length(local.all_recipients) > 0 ? join(" ", local.all_recipients) : ""

  # Jira: critical 状態時のみ起票。warning では起票しない (oncall 疲労を抑える設計)。
  # var.jira_project_key 空文字なら block 自体が空文字 → 起票無効。詳細は jira.tf。
  jira_handle = var.jira_project_key != "" ? "@jira-${var.jira_project_key}" : ""
  jira_block  = local.jira_handle != "" ? "{{#is_alert}}\n${local.jira_handle}\n{{/is_alert}}" : ""

  common_tags = [
    "env:${var.env}",
    "app:${var.app_name}",
    "team:${var.owner_team}",
    "managed-by:terraform",
  ]
}

# ----------------------------------------------------------------------------
# Backend: 5xx error rate > 1% in 5 min
# ----------------------------------------------------------------------------
resource "datadog_monitor" "backend_5xx_rate" {
  name    = "[${var.app_name}] backend 5xx rate"
  type    = "query alert"
  message = <<-EOT
    Backend が 5xx を 1% 以上返しています。
    最近の deploy / migration を確認してください。
    ${local.recipient_block}
    ${local.jira_block}
  EOT

  # OTel/FastAPI 計装が吐く HTTP status を resource_name で集計。trace metric が
  # まだ流れていない場合は最初の trace 到着後に正式 metric 名へ書換 (例:
  # trace.fastapi.request.errors{...}.as_count() を使う等)。
  query = "sum(last_5m):(sum:trace.backend.request.errors{service:backend,env:${var.env}}.as_count() / sum:trace.backend.request.hits{service:backend,env:${var.env}}.as_count()) > 0.01"

  monitor_thresholds {
    critical = 0.01
    warning  = 0.005
  }

  notify_no_data      = false
  require_full_window = false
  renotify_interval   = 60

  tags = concat(local.common_tags, ["service:backend", "category:errors"])
}

# ----------------------------------------------------------------------------
# Backend: LLM 推論レイテンシ p95 > 7 分 (CPU 推論 4-5 分が正常、+50% で alert)
# ----------------------------------------------------------------------------
resource "datadog_monitor" "llm_latency_p95" {
  name    = "[${var.app_name}] LLM inference p95 latency"
  type    = "query alert"
  message = <<-EOT
    LLM 推論レイテンシ p95 が 7 分 (420秒) を超えています。
    INF-006: CPU 推論の通常 p95 = 4-5 分 (~300秒)。
    Ollama / gemma4:e4b のヘルス、ホスト CPU、コンテナ mem_limit を確認。
    ${local.recipient_block}
    ${local.jira_block}
  EOT

  # OllamaLocalLLMClient.generate の span duration p95。実 metric 名は trace
  # 到着後に確認 — 仮で trace.* を使用。
  query = "avg(last_15m):p95:trace.backend.request{service:backend,env:${var.env},resource_name:POST_/api/generate} > 420000"

  monitor_thresholds {
    critical = 420000
    warning  = 360000
  }

  notify_no_data      = false
  require_full_window = false

  tags = concat(local.common_tags, ["service:backend", "category:latency", "subsystem:llm"])
}

# ----------------------------------------------------------------------------
# Frontend (browser): JS error rate > 5% of sessions in 10 min
# ----------------------------------------------------------------------------
# TODO: RUM Analytics formula query の syntax が API validate を通らない
# (`Invalid query: Check for invalid tags or facets`)。RUM data が流れ始めてから
# Datadog UI の Monitor → New → RUM で実値プレビュー → JSON export → ここへ転記。
# 一旦 comment out して他のリソースだけ apply する。
/*
resource "datadog_monitor" "frontend_rum_error_rate" {
  name    = "[${var.app_name}] frontend RUM error rate"
  type    = "rum alert"
  message = <<-EOT
    Frontend (browser) で 5% 以上のセッションが JS エラーを起こしています。
    最近の frontend deploy / 依存 upgrade を確認してください。
    PHI 観点: error.message は scrub 済 (lib/datadog-rum.ts) ですが Sample 件は
    マスク不足のないことを念のため確認。
    ${local.recipient_block}
    ${local.jira_block}
  EOT

  # RUM Analytics query — error session count / total session count > 0.05
  query = "formula(\"query1 / query2\").last(\"10m\") > 0.05"

  monitor_thresholds {
    critical = 0.05
    warning  = 0.02
  }

  variables {
    event_query {
      name        = "query1"
      data_source = "rum"
      indexes     = ["*"]
      compute {
        aggregation = "count"
      }
      search {
        query = "@type:session @session.has_error:true @service:frontend-browser @env:${var.env}"
      }
    }
    event_query {
      name        = "query2"
      data_source = "rum"
      indexes     = ["*"]
      compute {
        aggregation = "count"
      }
      search {
        query = "@type:session @service:frontend-browser @env:${var.env}"
      }
    }
  }

  notify_no_data      = false
  require_full_window = false

  tags = concat(local.common_tags, ["service:frontend-browser", "category:errors"])
}
*/

# ============================================================================
# 以下、推奨アラート追加分 (2026-05-24)
# - 通知先: var.monitor_recipients (terraform.tfvars に @slack-channel を設定)
# - 適用 env: var.env のみ (現状 local)
# - 閾値は PoC 想定の暫定値。1 週間ベースライン取得後に tighten。
# ============================================================================

# ----------------------------------------------------------------------------
# Backend: HTTP p95 latency > 2s (general endpoints, excl. LLM/ASR)
# ----------------------------------------------------------------------------
resource "datadog_monitor" "backend_latency_p95" {
  name    = "[${var.app_name}] backend HTTP p95 latency"
  type    = "query alert"
  message = <<-EOT
    Backend HTTP の p95 レイテンシが 2 秒を超えました。
    LLM/ASR の重い処理を除く一般 endpoint で遅延発生 — DB クエリ、N+1、外部 dependency を確認。
    ${local.recipient_block}
    ${local.jira_block}
  EOT

  # trace metric は ms 単位。LLM endpoint は別 monitor (llm_latency_p95) で監視。
  # /api/generate と /api/transcribe を除外して general latency に絞る。
  query = "avg(last_15m):p95:trace.backend.request{service:backend,env:${var.env},!resource_name:POST_/api/generate,!resource_name:POST_/api/transcribe} > 2000"

  monitor_thresholds {
    critical = 2000
    warning  = 1000
  }

  notify_no_data      = false
  require_full_window = false
  renotify_interval   = 60

  tags = concat(local.common_tags, ["service:backend", "category:latency"])
}

# ----------------------------------------------------------------------------
# ASR: whisper.cpp 推論 p95 > 60s
# ----------------------------------------------------------------------------
resource "datadog_monitor" "asr_latency_p95" {
  name    = "[${var.app_name}] ASR (whisper.cpp) p95 latency"
  type    = "query alert"
  message = <<-EOT
    ASR (whisper.cpp) の p95 レイテンシが 60 秒を超えました。
    録音長が長い場合は正常範囲。短い録音で発生していたら asr コンテナの CPU / メモリを `docker compose stats asr` で確認。
    ${local.recipient_block}
    ${local.jira_block}
  EOT

  # resource_name は backend の ASR endpoint。実 metric 名は trace 到着後に確認。
  query = "avg(last_15m):p95:trace.backend.request{service:backend,env:${var.env},resource_name:POST_/api/transcribe} > 60000"

  monitor_thresholds {
    critical = 60000
    warning  = 45000
  }

  notify_no_data      = false
  require_full_window = false

  tags = concat(local.common_tags, ["service:backend", "category:latency", "subsystem:asr"])
}

# ----------------------------------------------------------------------------
# Infra: llm container memory > 10 GiB (mem_limit 11 GiB の ~90%)
# ----------------------------------------------------------------------------
resource "datadog_monitor" "llm_container_memory" {
  name    = "[${var.app_name}] llm container memory near limit"
  type    = "query alert"
  message = <<-EOT
    llm (ollama) コンテナのメモリ使用が 10 GiB を超えました (mem_limit 11 GiB の ~90%)。
    INF-006 で過去に OOM Kill 発生実績あり。このまま伸びると llm コンテナが落ち、推論が即座に失敗します。
    確認: Ollama keep_alive 設定、モデル並列ロード、KV キャッシュサイズ。
    ${local.recipient_block}
    ${local.jira_block}
  EOT

  # 10737418240 bytes = 10 GiB
  query = "avg(last_5m):avg:docker.mem.rss{container_name:test-ai-app-llm-1,env:${var.env}} > 10737418240"

  monitor_thresholds {
    critical = 10737418240
    warning  = 9663676416
  }

  notify_no_data      = false
  require_full_window = false
  renotify_interval   = 30

  tags = concat(local.common_tags, ["service:llm", "category:saturation"])
}

# ----------------------------------------------------------------------------
# Infra: container restart loop (30 分以内に 3 回以上の再起動)
# ----------------------------------------------------------------------------
resource "datadog_monitor" "container_restart_loop" {
  name    = "[${var.app_name}] container restart loop"
  type    = "query alert"
  message = <<-EOT
    どこかのコンテナが 30 分以内に 3 回以上再起動しています (crash loop の兆候)。
    `docker compose logs <container_name>` で原因確認。典型: OOM Kill、health-check 失敗、entrypoint 例外。
    ${local.recipient_block}
    ${local.jira_block}
  EOT

  query = "sum(last_30m):sum:docker.containers.restarts{env:${var.env}} by {container_name}.as_count() > 3"

  monitor_thresholds {
    critical = 3
    warning  = 1
  }

  notify_no_data      = false
  require_full_window = false

  tags = concat(local.common_tags, ["category:reliability"])
}

# ----------------------------------------------------------------------------
# DB: PostgreSQL active connections > 80 (default max_connections=100 の 80%)
# ----------------------------------------------------------------------------
# ⚠️ 要 postgres integration 有効化 — docker-compose.yml の postgres service に
#    `com.datadoghq.ad.check_names=["postgres"]` ラベルと接続情報を追加するまで no data。
resource "datadog_monitor" "postgres_connections" {
  name    = "[${var.app_name}] PostgreSQL connections near pool exhaustion"
  type    = "query alert"
  message = <<-EOT
    PostgreSQL の active connections が 80 を超えました (default max_connections=100 の 80%)。
    SQLAlchemy プール枯渇、leaked connection、長時間 transaction を確認。
    ${local.recipient_block}
    ${local.jira_block}
  EOT

  query = "avg(last_5m):avg:postgresql.connections{env:${var.env}} > 80"

  monitor_thresholds {
    critical = 80
    warning  = 60
  }

  notify_no_data      = false
  require_full_window = false

  tags = concat(local.common_tags, ["service:postgres", "category:saturation"])
}

# ----------------------------------------------------------------------------
# Logs: ERROR log spike — 5 分間に 50 件超 (= ~10 件/分)
# ----------------------------------------------------------------------------
# ⚠️ 要 log forwarding opt-in — 各 service に `com.datadoghq.ad.logs` ラベルが必要。
#    現状 frontend のみ有効、backend は docker-compose.yml line 245 周辺 comment out。
resource "datadog_monitor" "error_log_spike" {
  name    = "[${var.app_name}] error log spike"
  type    = "log alert"
  message = <<-EOT
    ERROR レベルログが過去 5 分間に 50 件超 (~10 件/分)。
    Logs Explorer で `status:error env:${var.env}` を開き、どの service / 例外が増えているか確認。
    ${local.recipient_block}
    ${local.jira_block}
  EOT

  query = "logs(\"status:error env:${var.env}\").index(\"*\").rollup(\"count\").last(\"5m\") > 50"

  monitor_thresholds {
    critical = 50
    warning  = 25
  }

  notify_no_data      = false
  require_full_window = false

  tags = concat(local.common_tags, ["category:errors"])
}

# ============================================================================
# Container saturation (CPU / memory) — 全コンテナ multi-alert by container_name
# - Slack:  warning + critical 両方 (local.recipient_block, 全 transition 発火)
# - Jira:   critical のみ (local.jira_block で {{#is_alert}} ラップ)
# - llm 専用の絶対値 memory monitor (llm_container_memory) は INF-006 OOM 履歴の
#   トラッキング目的で残置。こちらは ratio (mem_limit 比) で全コンテナ網羅。
# 必要: DD Agent が docker.{cpu,mem}.* metrics を host から収集していること。
# ============================================================================

# ----------------------------------------------------------------------------
# Container CPU usage > 80% (multi-alert by container_name)
# ----------------------------------------------------------------------------
resource "datadog_monitor" "container_cpu_high" {
  name    = "[${var.app_name}] container CPU usage high — {{container_name.name}}"
  type    = "query alert"
  message = <<-EOT
    `{{container_name.name}}` の CPU 使用率が過去 10 分平均で 80% を超えました。
    確認: `docker compose stats {{container_name.name}}`、推論バッチ集中、CPU 専有プロセス。
    PoC ホスト想定 ~6 core。1 コンテナ単独で長時間占有すると他サービス (frontend / postgres) が starve します。
    ${local.recipient_block}
    ${local.jira_block}
  EOT

  # docker.cpu.usage は host CPU 全体に対する % (per container)。100% = 1 core 相当。
  query = "avg(last_10m):avg:docker.cpu.usage{env:${var.env}} by {container_name} > 80"

  monitor_thresholds {
    critical = 80
    warning  = 60
  }

  notify_no_data      = false
  require_full_window = false
  renotify_interval   = 60

  tags = concat(local.common_tags, ["category:saturation", "metric:cpu"])
}

# ----------------------------------------------------------------------------
# Container memory usage > 85% of mem_limit (multi-alert by container_name)
# ----------------------------------------------------------------------------
resource "datadog_monitor" "container_memory_high" {
  name    = "[${var.app_name}] container memory usage high — {{container_name.name}}"
  type    = "query alert"
  message = <<-EOT
    `{{container_name.name}}` のメモリ使用率が mem_limit の 85% を超えました。
    確認: `docker compose stats {{container_name.name}}`、リーク、KV cache 肥大、import 重複。
    放置すると OOM Kill で `container_restart_loop` も連鎖発火します。
    ${local.recipient_block}
    ${local.jira_block}
  EOT

  # docker.mem.in_use は (RSS / mem_limit) の比率 (0.0-1.0)。mem_limit 未設定コンテナは N/A。
  query = "avg(last_10m):avg:docker.mem.in_use{env:${var.env}} by {container_name} > 0.85"

  monitor_thresholds {
    critical = 0.85
    warning  = 0.70
  }

  notify_no_data      = false
  require_full_window = false
  renotify_interval   = 60

  tags = concat(local.common_tags, ["category:saturation", "metric:memory"])
}
