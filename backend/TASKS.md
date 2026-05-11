# Backend TASKS

Active task list for the backend. Each task is a Block per `docs/handoff-contract.md`. Generator owns this file (per `AGENTS.md` §3); Planner seeds initial tasks.

## How to add a task

1. Copy the Sample Task Block below; rename `## Sample: …` to `## <Feature title>`.
2. Fill every required field. `Open-questions` MUST be `_(none)_` before handoff.
3. Add a row to the Task Index. Use status values: `pending`, `in-progress`, `qa`, `done`, `blocked`.
4. On Evaluator pass, flip the row to `done`. Do not delete completed Blocks; they are the implementation log.

## Task Index

| ID      | Title             | Status | Gates Touched          | Owner     |
| ------- | ----------------- | ------ | ---------------------- | --------- |
| INF-001 | Runtime Topology  | done   | G0                     | Generator |
| BE-001  | Inference Adapter | qa     | G1, G2, G3, G4, G5, G7 | Generator |

Note: INF-NNN is the ID convention for infrastructure Blocks that cross all layers (compose, network, environment).

---

## Runtime Topology (INF-001)

- **Goal:** Deliver the single `docker-compose.yml` that pins the deployment shape — frontend, backend, postgres, llm — with only frontend (3000) and backend (8000) ports exposed to the host.
- **Inputs:**
  - SPEC.md#runtime-topology
  - docs/runbook-local-dev.md
- **Acceptance:**
  - [ ] Single `docker-compose.yml` runs frontend, backend, postgres, llm.
  - [ ] Only `frontend` (3000) and `backend` (8000) publish ports to the host.
  - [ ] `llm` and `postgres` are reachable only on the internal compose network.
  - [ ] `docker compose up -d` brings the system to healthy in ≤120 s on a developer machine after first boot.
- **Out-of-scope:** Production orchestration (k8s/Nomad/etc.), GPU-specific toolkit config, Alembic migrations.
- **Open-questions:** _(none)_
- **Inference Impact:** no
- **Data Sensitivity:** none
- **Gates Touched:** G0
- **Affected Layers:** _(infrastructure / compose only)_
- **Status:** done

---

## Inference Adapter (BE-001)

- **Goal:** Deliver the `app/infrastructure/llm/` package: `LocalLLMClient` Protocol, `OllamaLocalLLMClient` concrete implementation, `FakeLocalLLMClient` test double, `InferenceError` with masked context, and a `ping` heartbeat method so `main.py:/health` no longer imports `httpx` for LLM traffic.
- **Inputs:**
  - backend/SPEC.md#inference-adapter
  - SPEC.md#inference-layer-contract
  - .claude/rules/local-llm-and-phi.md
- **Acceptance:**
  - [ ] `app/infrastructure/llm/__init__.py` exports `LocalLLMClient` (Protocol/ABC).
  - [ ] `OllamaLocalLLMClient` implements it; talks to `http://llm:11434`.
  - [ ] `FakeLocalLLMClient` is the default in unit tests; deterministic outputs from a fixture map.
  - [ ] Configuration values (`LLM_BASE_URL`, `LLM_MODEL`, `LLM_TIMEOUT_S`) are read from environment, not hardcoded.
  - [ ] Errors raise `InferenceError` with a masked context. The raw prompt never appears in `__str__` or `__repr__`.
  - [ ] Streaming is exposed as an async iterator of `Chunk` (`text`, `done`, optional `confidence`).
  - [ ] `main.py:/health` routes the LLM readiness probe through `LocalLLMClient.ping()` — no direct `httpx` import for LLM traffic in `main.py`.
- **Out-of-scope:** Embeddings, function-calling, tool use, multi-model routing.
- **Open-questions:** _(none)_
- **Inference Impact:** yes; model `gemma4:e4b`; prompt ≤4k tokens, output ≤1.5k tokens; timeout 60 s generate / 120 s stream.
- **Data Sensitivity:** PHI; mask prompt/response before any logger call.
- **Gates Touched:** G1, G2, G3, G4, G5, G7
- **Affected Layers:** infrastructure, usecases
- **Status:** qa

---

## Sample: Patient lookup by MRN (BE-000)

- **Goal:** Implement `GET /patients?mrn=<value>` returning a single patient or 404.
- **Inputs:**
  - backend/SPEC.md#api-surface
  - backend/SPEC.md#persistence
  - SPEC.md#domain-glossary
- **Acceptance:**
  - [ ] Endpoint declared in `app/interfaces/routers/patients.py` with `response_model=PatientRead`.
  - [ ] Usecase `find_patient_by_mrn` orchestrates repository call.
  - [ ] Repository `PatientRepository.find_by_mrn` issues a single indexed query.
  - [ ] On miss, returns 404 with normalised error body; no MRN in the message.
  - [ ] Logging filter masks `mrn` in any logger output across the request.
  - [ ] Unit tests use `FakeLocalLLMClient` (none invoked here) and an in-memory repo; one integration test under `pytest -m integration` hits the real DB.
- **Out-of-scope:** Cross-tenant search, fuzzy match, audit-log row.
- **Open-questions:** _(none)_
- **Inference Impact:** no
- **Data Sensitivity:** PHI; mask MRN in logs and errors.
- **Gates Touched:** G1, G2, G3, G4, G6, G7
- **Affected Layers:** domain, usecases, infrastructure, interfaces
- **Status:** sample only — do not implement.
