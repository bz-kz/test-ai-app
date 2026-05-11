# Project: AI Medical Record Generator (Local LLM)

## 1. System Architecture & Handoff

This project uses a 3-agent harness defined in `.claude/agents/`:

- **Planner (Opus):** High-level design & scope. Owns `SPEC.md` (root + sub).
- **Generator (Sonnet):** Implementation in sprints. Owns `TASKS.md` (frontend + backend) and source code.
- **Evaluator (Opus):** Strict QA & Review against `docs/dod-and-gates.md`. Read/execute only — no `edit`.

Mid-flight gates: `cost-check`, `security-check`. All inter-agent prompts conform to `docs/handoff-contract.md`.

## 2. Context & Tech Stack

- **Scope:** Local-only PoC. The whole stack runs on a developer's `localhost` via `docker compose`; there is no remote / staging / production deployment target. Only `frontend` (3000) and `backend` (8000) publish to `localhost`; `postgres` and `llm` stay on the internal compose network. Anything that assumes managed cloud, CDN, load-balancer, or external DNS is out of scope unless an ADR explicitly broadens it.
- **Monorepo:** `/frontend` (Next.js 15+, TS, Tailwind), `/backend` (Python 3.12+, FastAPI), `/docs`.
- **Database:** PostgreSQL (compose service `postgres`, internal-only).
- **LLM:** Local Gemma 4 E4B served by Ollama (compose service `llm`, internal-only). Single tier — Ollama tag `gemma4:e4b`. Hosted-LLM SDKs are forbidden — see `.claude/rules/local-llm-and-phi.md`.
- **Infra:** Single `docker-compose.yml` runs frontend, backend, postgres, llm on a developer's local machine. See `docs/runbook-local-dev.md`.
- **Language:** Human chat in JP. Docs in EN (token saving, less drift). Code identifiers in EN. UI strings in JP. Code comments in JP, only when explaining the _why_.

## 3. Core Principles

- **Efficiency:** Show code first. Minimal prose. Use Opus only for Planner/Evaluator and complex design.
- **Reliability:** Strict type safety (no `any`, no untyped dicts at boundaries). DDD on backend, Atomic Design + Onion on frontend.
- **Harness Flow:**
  1. Read `SPEC.md` (root + sub) and `TASKS.md` for the current task Block.
  2. Implement one Block at a time.
  3. Run G0–G3 self-eval (`docs/dod-and-gates.md`).
  4. Invoke `security-check` / `cost-check` if the Block is PHI- or inference-touching.
  5. Commit, then hand off to Evaluator.
  6. On pass, mark `TASKS.md` row `done`.

## 4. Commands

- **Compose:** `docker compose up -d` | `docker compose ps --status running` | `docker compose logs -f <svc>`
- **Frontend:** `cd frontend && npm run dev` | `npm run build` | `npx tsc --noEmit` | `npx eslint .` | `npm test -- --run`
- **Backend:** `cd backend && uvicorn main:app --reload` | `pyright` | `ruff check .` | `pytest -q`
- **Git:** `git log --oneline -n 5` at session start to sync state. Never `git push` from an agent.

## 5. Coding Standards

### Frontend (Atomic Design + Onion)

- Components: `frontend/src/components/{atoms|molecules|organisms}`. Mapping in `frontend/SPEC.md`.
- Logic: API calls in `src/services/`, state/effects in `src/hooks/`. No `fetch` in components.
- Constants: Check `frontend/src/lib/constants.ts` before hardcoding.

### Backend (DDD + FastAPI)

- Layers: `app/domain → app/usecases → app/infrastructure → app/interfaces`. Direction enforced (see `backend/SPEC.md#layer-boundaries`).
- Validation: Pydantic models for every Request/Response body.
- Inference: only via `app/infrastructure/llm/` (`LocalLLMClient`).

## 6. Definition of Done (DoD)

Per-task gates live in `docs/dod-and-gates.md`. Summary:

- [ ] G0 Compose-up green (when applicable)
- [ ] G1 Type / G2 Lint / G3 Unit green (Generator)
- [ ] G4 Security / G5 Cost green (when PHI/inference)
- [ ] G6 Spec alignment / G7 Architecture green (Evaluator)
- [ ] `TASKS.md` row updated and a concise commit is made.

## 7. Subagents & Skills

- Role definitions: `.claude/agents/*.md`.
- Shared skills: `.claude/skills/*`.
- Project rules (binding, ADR-gated): `.claude/rules/*.md`.

## 8. Harness Reference Index

| Artefact            | Path                                 |
| ------------------- | ------------------------------------ |
| Project Spec (root) | `SPEC.md`                            |
| Frontend Spec       | `frontend/SPEC.md`                   |
| Backend Spec        | `backend/SPEC.md`                    |
| Cross-agent rules   | `AGENTS.md`                          |
| ADR index           | `NOTES.md`                           |
| ADR template        | `docs/adr/0000-template.md`          |
| Handoff contract    | `docs/handoff-contract.md`           |
| DoD & gates         | `docs/dod-and-gates.md`              |
| Local-dev runbook   | `docs/runbook-local-dev.md`          |
| PHI/LLM rule        | `.claude/rules/local-llm-and-phi.md` |
| Design system       | `DESIGN.md`                          |

## 9. Known issues to surface to the human

- `.claude/settings.json` `PostToolUse` currently registers the Edit|Write Prettier hook **twice** (in addition to the protect-files hook). Agents do not modify settings; the human should consolidate the duplicate.
