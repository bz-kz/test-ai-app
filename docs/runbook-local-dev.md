# Local Dev Runbook

Single-machine setup for the AI Medical Record Generator. Everything runs in Docker on a developer's local PC. Nothing in this runbook should reach the public internet at runtime except the model registry pull on first boot.

## Topology

```
docker-compose.yml
├── frontend      Next.js dev server         :3000
├── backend       FastAPI (uvicorn)          :8000
├── postgres      PostgreSQL                  :5432
└── llm           Gemma 4 E4B inference server :11434  (Ollama-compatible API)
```

All services share a single private bridge network. Only `frontend` and `backend` expose ports to the host; `postgres` and `llm` are reachable only inside the network.

## Prerequisites

- Docker Desktop or Docker Engine 25+
- `docker compose` v2 (built into Docker Desktop)
- Disk: 15 GB free (model weights + Postgres data volume)
- RAM: 16 GB recommended (8 GB minimum for CPU-only operation)
- GPU: optional. The E4B model is designed to run on modest hardware, including CPU-only.

## First boot

```bash
# 1. Build images and create the network/volumes.
docker compose build

# 2. Start everything detached.
docker compose up -d

# 3. Pull the Gemma model into the llm container (one-time).
#    Single supported model — no tier ladder.
docker compose exec llm ollama pull gemma4:e4b

# 4. Confirm health.
docker compose ps --status running
```

Expected: 4 services in `running (healthy)` state. If any service is `restarting`, jump to **Troubleshooting**.

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
```

All four MUST return success before declaring G0 (compose-up) green.

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

## Hardware-specific paths

### GPU (NVIDIA)

- Ensure the NVIDIA Container Toolkit is installed.
- The `llm` service in `docker-compose.yml` requests `gpus: all`.
- Verify with `docker compose exec llm nvidia-smi`. If empty, the toolkit is not wired.

### CPU-only operation

- No model swap is needed; `gemma4:e4b` runs on CPU.
- Expect ~3× slower inference vs the GPU baseline; if your features depend on the SPEC latency budget, file a temporary override Block via Planner.
- Lower `LLM_TIMEOUT_S` floor to 90 s for `generate` if you observe spurious timeouts on first request after pull.

## Troubleshooting

### `llm` container restarts on boot

Most often: model not yet pulled. The first generation request blocks while pulling, then times out the healthcheck. Run the `ollama pull` step explicitly before the first request.

### Backend cannot reach `llm`

Check the service hostname. From `backend`, the URL MUST be `http://llm:11434`, not `localhost`. `localhost` inside a container is the container itself.

### Postgres connection refused

The volume may be in a failed init state. Run:

```bash
docker compose down
docker volume ls | grep postgres
docker volume rm <volume-name>     # destructive: wipes DB
docker compose up -d
```

### Inference is slow / OOM

`gemma4:e4b` is the single supported model; there is no smaller tier to fall back to. Verify GPU memory pressure with `docker compose exec llm nvidia-smi`, lower the quantisation level (`Q4_0` is the project default) only via an ADR, and confirm the request body is not exceeding the prompt-length budget in `SPEC.md#inference-layer-contract`. Document any temporary mitigation as a `## Spec Pivot Request` Block.

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
