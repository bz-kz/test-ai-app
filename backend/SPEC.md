# Backend SPEC

Sub-spec for the FastAPI / Python 3.12+ backend. Extends, never overrides, the root `SPEC.md`. All sections below are Blocks per `docs/handoff-contract.md`.

## Backend Mission

- **Goal:** Expose a typed HTTP API that lets the frontend manage patients, encounters, and AI-assisted record drafts, with all inference routed through a local Gemma 4 E4B service and PHI confined to the local Docker network.
- **Inputs:**
  - SPEC.md#product-goal
  - SPEC.md#inference-layer-contract
  - .claude/rules/local-llm-and-phi.md
- **Acceptance:**
  - [ ] All Request/Response bodies are Pydantic models.
  - [ ] No domain code imports from `infrastructure` or `usecases`.
  - [ ] No infrastructure code calls a hosted-LLM SDK; all inference goes through `app/infrastructure/llm/`.
  - [ ] Logs never contain unmasked PHI.
- **Out-of-scope:** Multi-tenant auth, cloud LLM fallback, message-queue async pipelines.
- **Open-questions:** _(none)_
- **Data Sensitivity:** PHI

## Layer Boundaries

- **Goal:** Pin the DDD direction so import-graph violations are mechanically detectable.
- **Inputs:** _(none)_
- **Acceptance:**
  - [ ] `app/domain/` — pure types and business invariants. No imports from any other `app/` package.
  - [ ] `app/usecases/` — orchestrates domain + infrastructure. May import from `domain` and `infrastructure`. MUST NOT be imported by `interfaces` directly except via the FastAPI dependency wiring.
  - [ ] `app/infrastructure/` — adapters: DB (SQLAlchemy), LLM (`LocalLLMClient`), external clients. MUST NOT import from `usecases` or `interfaces`.
  - [ ] `app/interfaces/` — FastAPI routers, request/response Pydantic models, dependency declarations. MUST NOT import from `infrastructure` directly; goes through `usecases`.
  - [ ] Direction (allowed): `interfaces → usecases → infrastructure → domain` (each layer may also depend on `domain`).
- **Out-of-scope:** Hexagonal-port abstractions beyond what `LocalLLMClient` requires.
- **Open-questions:** _(none)_
- **Gates Touched:** G7
- **Affected Layers:** domain, usecases, infrastructure, interfaces

## Inference Adapter

- **Goal:** Make the local-Gemma adapter a thin, replaceable component the rest of the backend talks to without knowing the wire format.
- **Inputs:**
  - SPEC.md#inference-layer-contract
  - .claude/rules/local-llm-and-phi.md
- **Acceptance:**
  - [ ] `app/infrastructure/llm/__init__.py` exports `LocalLLMClient` (Protocol/ABC).
  - [ ] `OllamaLocalLLMClient` implements it; talks to `http://llm:11434`.
  - [ ] `FakeLocalLLMClient` is the default in unit tests; deterministic outputs from a fixture map.
  - [ ] Configuration values (`LLM_BASE_URL`, `LLM_MODEL`, `LLM_TIMEOUT_S`) are read from environment, not hardcoded.
  - [ ] Errors raise `InferenceError` with a masked context. The raw prompt never appears in `__str__` or `__repr__`.
  - [ ] Streaming is exposed as an async iterator of `Chunk` (`text`, `done`, optional `confidence`).
- **Out-of-scope:** Embeddings, function-calling, tool use.
- **Open-questions:** _(none)_
- **Inference Impact:** yes
- **Data Sensitivity:** PHI
- **Gates Touched:** G4, G5, G7
- **Affected Layers:** infrastructure, usecases

## Persistence

- **Goal:** Define the storage shape for patient/encounter/record data so PHI columns are explicit and masking-on-log is enforceable.
- **Inputs:**
  - SPEC.md#domain-glossary
- **Acceptance:**
  - [ ] Tables: `patient`, `encounter`, `record_draft`, `record_final`, `audit_log`.
  - [ ] PHI columns flagged via a `phi=True` SQLAlchemy column-info marker; the logging filter masks any value carrying it.
  - [ ] `record_final` rows are immutable (no UPDATE allowed; corrections are new rows referencing predecessors).
  - [ ] All persistence goes through repositories in `app/infrastructure/db/`. No raw SQL in `usecases` or `interfaces`.
  - [ ] Migrations live under `backend/migrations/` with Alembic. Each migration is reviewed against PHI implications.
- **Out-of-scope:** Read replicas, sharding, OLAP exports.
- **Open-questions:** _(none)_
- **Data Sensitivity:** PHI
- **Gates Touched:** G4, G7
- **Affected Layers:** infrastructure, usecases

## API Surface

- **Goal:** Anchor the public HTTP shape so the frontend can be implemented in parallel.
- **Inputs:**
  - frontend/SPEC.md#frontend-mission
- **Acceptance:**
  - [ ] All endpoints declared with FastAPI `response_model=`; no untyped responses.
  - [ ] Errors normalised to `{ "code": str, "message": str }`; messages never include PHI.
  - [ ] `/health` returns 200 when Postgres and llm are both reachable; 503 otherwise.
  - [ ] OpenAPI is generated; the `docs/` static site is NOT exposed in production builds.
- **Out-of-scope:** GraphQL, WebSocket transport (if needed, file an ADR).
- **Open-questions:** _(none)_
- **Gates Touched:** G1, G2, G6, G7
- **Affected Layers:** interfaces

## Default Gates

Every backend feature task sets at minimum: `Gates Touched: G1, G2, G3, G6, G7`. Add G4 for any task that touches PHI columns, prompts, or logging. Add G5 for any task that exercises the inference path. Add G0 when `docker-compose.yml`, base image, or migrations are touched.

## Recap of cross-cutting rules (binding)

- Pydantic at every interface boundary; no untyped dicts cross layers.
- No `# type: ignore` without an inline reason and a follow-up note in `NOTES.md`.
- Logging uses the project logger; never `print` in committed code.
- Tests: unit tests use `FakeLocalLLMClient` and a transactional Postgres fixture. Integration tests against the real `llm` container live behind a `pytest -m integration` marker.
