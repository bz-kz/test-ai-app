# AI Medical Record Generator

> Local-only PoC. A clinician drafts, edits, and finalises medical records faster by streaming SOAP drafts and Japanese voice transcription from models that run entirely inside `docker compose` on a developer laptop. **No PHI ever leaves the local network.**

## Status

Single-developer proof-of-concept. Not for production use. There is no remote / staging / cloud target — see `CLAUDE.md` §2 and `.claude/rules/local-deployment-discipline.md`.

## Topology

```
docker-compose.yml
├── frontend    Next.js 15 (TS, Tailwind)               :3000   (host-published)
├── backend     FastAPI / Python 3.12+                  :8000   (host-published)
├── postgres    PostgreSQL 16                           :5432   (internal-only)
├── llm         Ollama serving gemma4:e4b               :11434  (internal-only)
└── asr         whisper.cpp medium-q5_0 (server)        :8080   (internal-only)
```

All services share one private bridge network. Only `frontend` and `backend` publish to the host; `postgres`, `llm`, and `asr` are unreachable from outside the compose network. This is binding — see `.claude/rules/local-llm-and-phi.md` §1.

## Capabilities

- MRN-based patient search → encounter creation → SOAP draft → finalised record chain.
- **SSE-streamed SOAP draft generation** from raw clinical input via a local Gemma 4 E4B model.
- **Japanese voice transcription** (WebM/Opus upload → 16 kHz PCM → whisper.cpp); both single-shot and chunked-streaming endpoints (`ADR-0003`, opt-in via `NEXT_PUBLIC_ASR_STREAMING_ENABLED`).
- Draft edit / regenerate / finalise / correct chain with audit metadata.
- Clinician is always the editor of last resort — the system never auto-finalises.

## Prerequisites

- Docker Desktop or Docker Engine 25+, `docker compose` v2.
- 15 GB free disk (model weights + Postgres volume).
- **24 GB system RAM** recommended; Docker Desktop memory slider ≥ 13 GB (gemma `~10 GiB` + whisper `~1 GiB` + overhead `~2 GiB`).
- CPU-only is supported; expect ≥3× slower inference vs. a GPU baseline. GPU optional (NVIDIA Container Toolkit + ≥10 GB VRAM).

Full prerequisite list + first-boot steps live in `docs/runbook-local-dev.md`.

## Quick start

```bash
# Build + start everything detached.
docker compose build
docker compose up -d

# Wait for postgres to become healthy, then apply migrations.
docker compose exec backend alembic upgrade head

# One-time model pull (~10 GB; subsequent boots reuse the volume).
docker compose exec llm ollama pull gemma4:e4b

# ASR weights (~0.7 GB) are downloaded automatically on first boot of the asr service.
docker compose ps --status running   # expect 5 services
```

Open <http://localhost:3000>. Health checks:

```bash
curl -fsS http://localhost:8000/health    # backend
curl -fsS http://localhost:3000/api/health # frontend
```

After backend or frontend code changes the image MUST be rebuilt (`local-deployment-discipline.md` §1):

```bash
docker compose build backend  && docker compose up -d backend
docker compose build frontend && docker compose up -d frontend
```

`--force-recreate` alone does **not** pick up new source — `up -d` only re-creates the container from the existing image.

## Repository layout

```
frontend/                         Next.js 15 app (App Router, Atomic Design + Onion)
  src/app/                          Routes (/, /patients, /encounters, /draft)
  src/components/{atoms,molecules,organisms}
  src/services/                     HTTP layer (fetch lives here only)
  src/hooks/                        State + effects
backend/                          FastAPI app (DDD)
  app/domain/                       Pure domain entities (no deps)
  app/usecases/                     Orchestration; only layer that constructs LLM/ASR clients
  app/infrastructure/               Postgres, Ollama, whisper.cpp adapters
    llm/                              LocalLLMClient + OllamaLocalLLMClient
    asr/                              LocalASRClient + WhisperCppLocalASRClient
  app/interfaces/                   FastAPI routers + Pydantic Request/Response models
docker/asr/                       whisper.cpp multi-stage build (arm64 + amd64)
docs/
  runbook-local-dev.md              Operator step-by-step
  adr/                              Accepted ADRs (binding)
  handoff-contract.md               Inter-agent message shape
  dod-and-gates.md                  G0–G7 definition
.claude/
  agents/                           Planner / Generator / Evaluator definitions
  rules/                            Binding project rules (ADR-gated)
  skills/                           Shared agent skills
SPEC.md                           Project-level spec (root)
frontend/SPEC.md, backend/SPEC.md Sub-specs
CLAUDE.md                         Coding standards + harness flow
AGENTS.md                         Inter-agent rules incl. git policy
NOTES.md                          ADR index
DESIGN.md                         Visual + AI-output design language
```

## Engineering rules (binding)

These are non-negotiable. Violations stop the harness loop and require an ADR before resuming.

- **PHI + local inference:** `.claude/rules/local-llm-and-phi.md`
  - No hosted-LLM SDKs (OpenAI / Anthropic / Bedrock / etc.) at runtime.
  - All inference goes through `app/infrastructure/llm/`; all ASR through `app/infrastructure/asr/`.
  - PHI must not appear in INFO/WARNING/ERROR logs, `localStorage`, `sessionStorage`, `IndexedDB`, or URL params.
  - PHI-bearing buffers in React live in `useRef`, never `useState` (ADR-0004).
- **Architecture layer direction:** `.claude/rules/architecture-layer-direction.md`
  - Backend: `interfaces → usecases → infrastructure → domain` (inwards only).
  - Frontend: pages → hooks → services. Atoms never fetch.
- **Local deployment discipline:** `.claude/rules/local-deployment-discipline.md`
  - `NEXT_PUBLIC_*` must be declared in **both** `build.args` and `environment:` of `docker-compose.yml` (Next.js bakes them at build time).
  - `docker compose build <svc> && up -d <svc>` after every code change; never `--force-recreate` to "pick up new code".
- **Git policy** (`AGENTS.md` §8 + ADR-0005)
  - Direct `git push origin main` is forbidden and protected on GitHub. Agents may push to non-default branches and open PRs; only a human merges.
  - Commit messages use conventional prefixes (`feat:` `fix:` `refactor:` `test:` `docs:` `chore:`) and stay ≤72 chars on the subject line.

## Daily commands

```bash
# Compose
docker compose up -d
docker compose down                 # keep volumes
docker compose down -v              # destructive — wipes DB + model cache
docker compose logs -f backend
docker compose restart backend      # only useful when the image is already current

# Frontend (host shell)
cd frontend && npm run dev          # dev server
npx tsc --noEmit                    # type check
npx eslint .                        # lint
npx vitest run                      # tests

# Backend (host shell with backend/.venv)
cd backend
.venv/bin/ruff check .
.venv/bin/pyright .
.venv/bin/pytest -q
```

## Definition of Done

Each task closes against `docs/dod-and-gates.md`. Summary:

- G0 Compose-up green (when applicable)
- G1 Type / G2 Lint / G3 Unit green (Generator)
- G4 Security / G5 Cost green (when PHI- or inference-touching)
- G6 Spec alignment / G7 Architecture green (Evaluator)
- `TASKS.md` row marked `done` and a concise commit landed.

## Harness (Planner → Generator → Evaluator)

This repo uses a 3-agent harness with mid-flight `security-check` and `cost-check` skills. Roles, gates, and handoff shape live in:

- `.claude/agents/*.md` — agent role definitions.
- `docs/handoff-contract.md` — message shape between agents.
- `docs/dod-and-gates.md` — per-gate ownership.
- `AGENTS.md` — cross-agent rules including the git policy.

## Reference docs

- [`SPEC.md`](SPEC.md) — product spec (root). Sub-specs in [`frontend/SPEC.md`](frontend/SPEC.md), [`backend/SPEC.md`](backend/SPEC.md).
- [`docs/runbook-local-dev.md`](docs/runbook-local-dev.md) — operator runbook (start, smoke, troubleshoot).
- [`NOTES.md`](NOTES.md) — ADR index.
- [`DESIGN.md`](DESIGN.md) — visual + AI-output design language.
- [`CLAUDE.md`](CLAUDE.md) — coding standards + harness flow (read this if you are coding here).

## Out of scope

- Production deployment, cloud LLM fallback, multi-tenant isolation, mobile-native client, EHR/billing integration. Each would require an ADR amending `SPEC.md`.
