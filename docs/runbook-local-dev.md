# Local Dev Runbook

Single-machine setup for the AI Medical Record Generator. Everything runs in Docker on a developer's local PC. Nothing in this runbook should reach the public internet at runtime except the model registry pull on first boot.

## Topology

```
docker-compose.yml
├── frontend         Next.js dev server                  :3000
├── backend          FastAPI (uvicorn + OTel auto-inst)  :8000
├── postgres         PostgreSQL                          :5432  (internal-only)
├── llm              Gemma 4 E4B (Ollama)                :11434 (internal-only)
├── asr              whisper.cpp medium-q5_0 server      :8080  (internal-only)
├── otel-collector   OTel Collector contrib (datadog exp):4318  (internal-only) — ADR-0006
└── datadog-agent    DD Agent 7.66.1 (metrics/logs)     4317/4318/8125/8126 (host-exposed)
```

All services share a single private bridge network. `frontend` (3000) and `backend` (8000) expose ports to the host; `datadog-agent` exposes 4317/4318/8125/8126 to the host for direct dev probes. `postgres`, `llm`, `asr`, `otel-collector` are reachable only inside the network.

Traces flow: app OTel SDK → `otel-collector:4318` → Datadog SaaS (datadog exporter). DD Agent's own OTLP receiver is NOT in the trace path because the 7.66.1 OTLP→APM bridge is broken on this stack — see ADR-0006 §Decision and `docker/otel-collector/config.yaml`.

## Prerequisites

- Docker Desktop or Docker Engine 25+
- `docker compose` v2 (built into Docker Desktop)
- `.env` at repo root with at least: `DD_API_KEY`, `DD_SITE`. Add `DD_APP_KEY` if you intend to run `terraform/datadog/` (Datadog management API needs the App Key — separate from API Key, issued at Datadog UI → Organization Settings → Application Keys).
- For RUM (browser) verification: a Datadog RUM Application is required. Create one via `terraform/datadog/` (recommended) or manually in Datadog UI → UX Monitoring → RUM Applications. Populate `NEXT_PUBLIC_DD_RUM_APPLICATION_ID` / `NEXT_PUBLIC_DD_RUM_CLIENT_TOKEN` in `.env`.
- Disk: 15 GB free (model weights + Postgres data volume)
- **System RAM: 24 GB recommended.** The publisher-supplied `gemma4:e4b` Ollama tag loads ≈10 GiB at runtime (≈9.4 GiB weights + KV cache + compute graph), and the `llm` container needs that plus headroom alongside backend / postgres / frontend / Docker overhead. See `SPEC.md#hardware-assumptions`.
- **Docker Desktop memory allocation: ≥ 13 GB.** On macOS / Windows, open Docker Desktop → Settings → Resources → Memory and confirm the slider is ≥ 13 GB. This covers `gemma4:e4b` (~10 GiB) + `whisper.cpp medium-q5_0` (~1 GiB) + backend/postgres/frontend/Docker overhead (~2 GiB). Below 13 GB the `llm` container may fail to load with `model requires more system memory than is available` (see INF-003 history). 16 GB is recommended for comfortable headroom and for the kotoba-whisper variant swap described in ADR-0001.
- GPU: optional. With a GPU and ≥10 GB VRAM the same ~10 GiB footprint is paid in VRAM rather than system RAM. The model also runs CPU-only on the reference RAM allocation above (latency ≥3× slower vs GPU per SPEC).

## First boot

```bash
# 1. Build images and create the network/volumes.
docker compose build

# 2. Start everything detached.
docker compose up -d

# 3. Apply database migrations (required on first boot and after schema changes).
#    Wait until postgres is healthy before running this step.
docker compose exec backend alembic upgrade head

# 4. Pull the Gemma model into the llm container (one-time).
#    Single supported model — no tier ladder.
docker compose exec llm ollama pull gemma4:e4b

# 5. The asr service downloads ggml-medium-q5_0.bin (~0.7 GiB) automatically on first
#    boot from HuggingFace. This happens inside the container at startup — no manual
#    step required, but the first `docker compose up -d` after INF-004 lands will be
#    slow while the model downloads. The asr healthcheck has a 120 s start_period to
#    accommodate this. Subsequent starts skip the download (model is in asr_data volume).

# 6. Confirm health (expect 7 services running).
docker compose ps --status running
```

Expected: 7 services in `running` or `running (healthy)` state (frontend, backend, postgres, llm, asr, otel-collector, datadog-agent). If any service is `restarting`, jump to **Troubleshooting**.

> **Port mapping summary** (useful when reading `docker compose ps` output):
>
> - `frontend` :3000 → host :3000
> - `backend` :8000 → host :8000
> - `postgres` :5432 → internal only
> - `llm` :11434 → internal only
> - `asr` :8080 → internal only (whisper-server; no host exposure per PHI rule §1)

### Schema reset (destructive)

If the database schema needs to be reset during development (e.g. after changing migrations):

```bash
# WARNING: destroys all data in the postgres volume.
docker compose down -v
docker compose up -d
docker compose exec backend alembic upgrade head
```

## Health checks

```bash
# Backend
curl -fsS http://localhost:8000/health

# Frontend
curl -fsS http://localhost:3000/api/health

# Postgres (from inside the network)
docker compose exec backend pg_isready -h postgres -U app

# LLM smoke test (smallest possible prompt, ASCII only — no PHI)
docker compose exec backend curl -fsS http://llm:11434/api/generate \
  -d '{"model":"gemma4:e4b","prompt":"ping","stream":false}'

# ASR readiness check (TCP port only — no audio, no PHI)
docker compose exec backend python3 -c \
  "import socket; s=socket.socket(); s.settimeout(4); s.connect(('asr',8080)); s.close(); print('asr:8080 reachable')"

# OTel Collector readiness (trace path entry point — ADR-0006)
docker compose exec backend python3 -c \
  "import socket; s=socket.socket(); s.settimeout(4); s.connect(('otel-collector',4318)); s.close(); print('otel-collector:4318 reachable')"

# DD Agent (Datadog APM intake direct from host, for dev probes)
curl -fsS http://localhost:4318/v1/traces -X POST -d '' -o /dev/null -w "dd-agent OTLP: HTTP %{http_code}\n"  # 200 expected
```

All MUST return success before declaring G0 (compose-up) green.

## Daily commands

```bash
docker compose up -d                     # start
docker compose down                      # stop, keep volumes
docker compose down -v                   # stop, wipe DB and model cache (destructive)
docker compose logs -f backend           # tail one service
docker compose logs -f --tail=200        # tail everything
docker compose restart backend           # restart after code change without rebuild
docker compose exec backend bash         # shell into a service
```

## After a backend or frontend code change

The `frontend` and `backend` images are built from source via multi-stage Dockerfiles, so running containers do NOT pick up source-tree edits. After committing a backend or frontend Block, rebuild the changed service so the runtime matches the new code:

```bash
# Backend code change (any feature/bugfix Block under backend/app/**)
docker compose build backend && docker compose up -d backend

# Frontend code change (any feature/bugfix Block under frontend/src/**)
docker compose build frontend && docker compose up -d frontend
```

If you skip this step the browser (or `curl`) hits the pre-build image. Symptoms include 405/404 for endpoints declared in the new Block, or the UI showing the pre-edit JSX. The FE-006 verification surfaced this trap (the running backend container was stale by two Blocks because rebuild had not been triggered after BE-008 and BE-009).

> A migration or schema change additionally requires `docker compose exec backend alembic upgrade head` — see _First boot_ above.

## Hardware-specific paths

### GPU (NVIDIA)

- The reference `docker-compose.yml` **does not** request a GPU. The default path is CPU-only.
- To opt in to GPU: install the NVIDIA Container Toolkit, then add a `deploy.resources.reservations.devices` block to the `llm` service (or add `gpus: all` under `llm` if using legacy Compose v1 syntax). After the edit, `docker compose up -d --build llm` and verify with `docker compose exec llm nvidia-smi`.
- Without that edit, `docker compose exec llm nvidia-smi` will fail or be empty — the toolkit is fine; the service simply hasn't been asked to reserve a device.

### CPU-only operation

- No model swap is needed; `gemma4:e4b` runs on CPU. This is the default in `docker-compose.yml`.
- Expect ≥3× slower inference vs the GPU baseline. Measured CPU operating point (Playwright reproduction 2026-05-13, PR #13 / INF-006): first-token ~2–3 min, total ~4–5 min. The SPEC L96 budget (≤1 s TTFT / ≤6 s total) is the aspirational GPU target; the gap is structural and requires an ADR (GPU offload / hosted LLM / quantization A/B) to close.
- `LLM_TIMEOUT_S` is set to `600` in `docker-compose.yml` (PR #13 / INF-006 raised it from `300`; previously raised from the 60 / 120 s defaults in commit `fa04bae` / INF-003). The stream timeout is `LLM_TIMEOUT_S × 2 = 1200` s per `ollama_client.stream()`. Raise further only if the first request after a fresh model pull is still timing out; never lower below 600 s on CPU.

## Troubleshooting

### `llm` container restarts on boot

Most often: model not yet pulled. The first generation request blocks while pulling, then times out the healthcheck. Run the `ollama pull` step explicitly before the first request.

### `asr` container is unhealthy / slow to start

On first boot the `asr` container downloads `ggml-medium-q5_0.bin` (~0.7 GiB) from HuggingFace before starting `whisper-server`. The healthcheck has a 120 s `start_period` to accommodate this. If the download is slow, the container will appear unhealthy temporarily — wait for the model download to complete. Check progress with:

```bash
docker compose logs -f asr
```

If the download fails (network issue), the model file may be incomplete. Remove it and restart:

```bash
docker compose down asr
docker volume rm $(docker volume ls -q | grep asr_data)
docker compose up -d asr
```

### Backend cannot reach `llm` or `asr`

Check the service hostname. From `backend`, the LLM URL MUST be `http://llm:11434` and the ASR URL MUST be `http://asr:8080`, never `localhost`. `localhost` inside a container is the container itself.

### Postgres connection refused

The volume may be in a failed init state. Run:

```bash
docker compose down
docker volume ls | grep postgres
docker volume rm <volume-name>     # destructive: wipes DB
docker compose up -d
```

### Inference is slow / OOM

`gemma4:e4b` is the single supported model; there is no smaller tier to fall back to. On the default CPU path verify pressure with `docker stats --no-stream` and watch the `llm` container's `MEM USAGE / LIMIT` row — `mem_limit: 11g` (INF-006) bounds the OOM blast radius to the `llm` service. If a GPU has been wired manually (see the GPU subsection above), `docker compose exec llm nvidia-smi` additionally shows VRAM. The tag is loaded at its publisher-supplied default precision — the project does NOT re-quantise (see `SPEC.md#hardware-assumptions`); any quantisation change requires an ADR amending that section. Confirm the request body is not exceeding the prompt-length budget in `SPEC.md#inference-layer-contract`. Document any temporary mitigation as a `## Spec Pivot Request` Block.

### A request returned PHI in a log line

Stop the affected service immediately:

```bash
docker compose stop backend
```

File an incident note in `NOTES.md` and link it from a new ADR before restarting. See `.claude/rules/local-llm-and-phi.md` for masking requirements.

## What this runbook deliberately does NOT do

- Production deployment. Production is out of scope for the current SPEC.
- Cloud LLM fallback. Forbidden by `.claude/rules/local-llm-and-phi.md`.
- Multi-tenant isolation. Single-developer assumption holds.

When any of these become in-scope, write a new runbook rather than extending this one.
