# Backend TASKS

Active task list for the backend. Each task is a Block per `docs/handoff-contract.md`. Generator owns this file (per `AGENTS.md` §3); Planner seeds initial tasks.

## How to add a task

1. Copy the Sample Task Block below; rename `## Sample: …` to `## <Feature title>`.
2. Fill every required field. `Open-questions` MUST be `_(none)_` before handoff.
3. Add a row to the Task Index. Use status values: `pending`, `in-progress`, `qa`, `done`, `blocked`.
4. On Evaluator pass, flip the row to `done`. Do not delete completed Blocks; they are the implementation log.

## Task Index

| ID      | Title               | Status | Gates Touched          | Owner     |
| ------- | ------------------- | ------ | ---------------------- | --------- |
| INF-001 | Runtime Topology    | done   | G0                     | Generator |
| BE-001  | Inference Adapter   | done   | G1, G2, G3, G4, G5, G7 | Generator |
| BE-002  | Persistence         | done   | G1, G2, G3, G4, G6, G7 | Generator |
| BE-003  | API Surface         | done   | G1, G2, G3, G4, G6, G7 | Generator |
| BE-004  | Patient endpoints   | done   | G1, G2, G3, G4, G6, G7 | Generator |
| BE-005  | Encounter endpoints | done   | G1, G2, G3, G4, G6, G7 | Generator |

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
- **Status:** done

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

---

## Persistence (BE-002)

- **Goal:** Deliver the storage layer for patient/encounter/record data with PHI columns explicitly flagged, `record_final` immutability enforced at two levels, repositories in `app/infrastructure/db/`, and Alembic migrations under `backend/migrations/`.
- **Inputs:**
  - backend/SPEC.md#persistence
  - SPEC.md#domain-glossary
  - .claude/rules/local-llm-and-phi.md
- **Acceptance:**
  - [ ] Tables: `patient`, `encounter`, `record_draft`, `record_final`, `audit_log`.
  - [ ] PHI columns flagged via `MappedColumn(info={"phi": True})`; logging filter masks values carrying the flag.
  - [ ] `record_final` rows are immutable: SQLAlchemy `before_flush` event rejects UPDATE; `RecordFinalRepository` has no `update_*` method.
  - [ ] All persistence goes through repositories in `app/infrastructure/db/`. No raw SQL in `usecases` or `interfaces`.
  - [ ] Migrations live under `backend/migrations/` (Alembic). Initial migration creates all 5 tables; PHI columns noted in migration header comment.
- **Out-of-scope:** Patient search endpoints, MRN normalization, read replicas, OLAP, BE-003 API Surface.
- **Open-questions:** _(none)_
- **Inference Impact:** no
- **Data Sensitivity:** PHI; PHI column values masked before any logger call via `PhiLoggingFilter`.
- **Gates Touched:** G1, G2, G3, G4, G6, G7
- **Affected Layers:** infrastructure, usecases
- **Status:** done

---

## API Surface (BE-003)

- **Goal:** Anchor the public HTTP shape so feature endpoints can be built consistently: router skeleton, normalised error envelope, Pydantic conventions demonstrated, and existing `/health`+`/ping` behaviour preserved.
- **Inputs:**
  - backend/SPEC.md#api-surface
  - backend/SPEC.md#layer-boundaries
  - frontend/SPEC.md#frontend-mission
  - .claude/rules/local-llm-and-phi.md
  - backend/main.py — current `/ping`, `/health` definitions; do not regress
- **Acceptance:**
  - [ ] `app/interfaces/routers/` exists with an `__init__.py`; routers mountable via `app.include_router(...)`.
  - [ ] Global exception handler returns `{ "code": str, "message": str }` for HTTPException, RequestValidationError (422), and unhandled Exception (500).
  - [ ] `code` values are stable machine identifiers; `message` MUST NOT echo PHI from request body.
  - [ ] All current endpoints declare `response_model=`; `/health` and `/ping` continue to behave per BE-001 contract.
  - [ ] OpenAPI reachable at `/openapi.json` in dev; `docs_url=None` / `redoc_url=None` stay set.
  - [ ] `ErrorResponse(BaseModel)` is the canonical error type referenced by every error handler.
  - [ ] Error handlers log through project logger; body fields passed through `mask_phi` before any logger call; 500 handler logs at `error` level with request path, body scrubbed.
  - [ ] Unit tests cover: HTTPException → envelope; 422 → `code="validation_error"`; unhandled → `code="internal_error"`, no PHI leakage; response_model strips extra fields.
- **Out-of-scope:** GraphQL, WebSocket, SSE, auth/authorization, feature endpoints (patient/encounter/record), CORS hardening beyond current state.
- **Open-questions:** _(none)_
- **Inference Impact:** no
- **Data Sensitivity:** PHI; error envelopes and 5xx logs MUST NOT include PHI from request body; use `mask_phi` for any value from request body that may carry PHI.
- **Gates Touched:** G1, G2, G3, G4, G6, G7
- **Affected Layers:** interfaces
- **Status:** done

---

## Patient endpoints (BE-004)

- **Goal:** Deliver the first feature surface — create a patient and look them up — using the existing `PatientRepository`, `AuditLogRepository`, and `app/interfaces/exception_handlers.py`. Three endpoints: POST `/patients` to create (with audit log), GET `/patients/{id}` to fetch by UUID, GET `/patients` with required query `?mrn=<value>` to fetch by MRN. All PHI fields handled per `.claude/rules/local-llm-and-phi.md`.
- **Inputs:**
  - backend/SPEC.md#api-surface — error envelope, response_model rule
  - backend/SPEC.md#layer-boundaries — DDD direction
  - backend/SPEC.md#persistence — PatientRepository, AuditLogRepository, ORM models
  - SPEC.md#domain-glossary — canonical identifiers (`patient`, `mrn`)
  - .claude/rules/local-llm-and-phi.md — PHI in prompts/logs/storage
  - backend/app/domain/entities.py — `Patient`, `AuditAction.PATIENT_CREATE`
  - backend/app/infrastructure/db/repositories.py — `PatientRepository.add/find_by_id/find_by_mrn`, `AuditLogRepository.append`
  - backend/app/interfaces/exception_handlers.py — existing `{code, message}` envelope and `ErrorResponse`
  - backend/main.py — currently mounts no feature routers
- **Acceptance:**
  - [ ] Usecases: `app/usecases/patient.py` exports `create_patient`, `find_patient_by_id`, `find_patient_by_mrn`; orchestrate repos; own UUID/timestamp generation; no raw SQL; no imports from `interfaces`.
  - [ ] Router: `app/interfaces/routers/patients.py` exposes POST `/patients` (201), GET `/patients/{patient_id}` (200/404), GET `/patients?mrn=` (200/404); mounted in `main.py`.
  - [ ] Pydantic models: `PatientCreate` (mrn, family_name, given_name, date_of_birth) and `PatientRead` (+ id, created_at).
  - [ ] PHI: mrn/family_name/given_name/date_of_birth masked via `mask_phi` before any logger call; error messages MUST NOT echo PHI values.
  - [ ] Audit log: `create_patient` writes one `AuditLog` with `AuditAction.PATIENT_CREATE` in same transaction; placeholder clinician UUID constant `_PLACEHOLDER_CLINICIAN_ID`.
  - [ ] DI: `get_session` from engine.py; repos constructed in router and passed into usecases.
  - [ ] Unit tests: `tests/usecases/test_patient.py` and `tests/interfaces/test_patients_router.py` per spec.
  - [ ] `response_model=PatientRead` on every endpoint; OpenAPI enriched with 404/409 error models.
- **Out-of-scope:** Patient update/delete, list/pagination, soft delete, fuzzy MRN match, auth, encounter/draft/final endpoints, migration changes.
- **Open-questions:** _(none)_
- **Inference Impact:** no
- **Data Sensitivity:** PHI; mrn/family_name/given_name/date_of_birth masked before any logger call; error messages MUST NOT echo PHI values.
- **Gates Touched:** G1, G2, G3, G4, G6, G7
- **Affected Layers:** usecases (new), interfaces (new router)
- **Status:** done

---

## Encounter endpoints (BE-005)

- **Goal:** Deliver the encounter feature surface — create an encounter (verifying the referenced patient exists), look one up by id, and list encounters for a patient. Three endpoints: POST `/encounters`, GET `/encounters/{encounter_id}`, GET `/patients/{patient_id}/encounters`.
- **Inputs:**
  - backend/SPEC.md#api-surface — error envelope, response_model rule
  - backend/SPEC.md#layer-boundaries — DDD direction
  - backend/SPEC.md#persistence — EncounterRepository, PatientRepository, AuditLogRepository
  - SPEC.md#domain-glossary — `encounter` canonical identifier; `clinician_id` is the actor
  - .claude/rules/local-llm-and-phi.md — encounter linkage to a patient is PHI; mask in logs
  - backend/app/domain/entities.py — `Encounter`, `AuditAction.ENCOUNTER_CREATE`
  - backend/app/infrastructure/db/repositories.py — repository implementations
  - backend/app/usecases/di.py — existing DI seam to extend
  - backend/app/usecases/errors.py — `MRNConflict` precedent; add new typed exceptions here
  - backend/app/interfaces/routers/patients.py — pattern to follow
  - backend/app/interfaces/exception_handlers.py — global `{code, message}` envelope
- **Acceptance:**
  - [ ] New module `app/usecases/encounter.py` exports `create_encounter`, `find_encounter_by_id`, `list_encounters_by_patient`.
  - [ ] `create_encounter` raises `PatientNotFound` when patient does not exist; writes one AuditLog with `action=AuditAction.ENCOUNTER_CREATE`, `meta_json="{}"`, no PHI; patient and encounter INSERT in same transaction.
  - [ ] `app/usecases/di.py` extended with `make_create_encounter`, `make_find_encounter_by_id`, `make_list_encounters_by_patient`.
  - [ ] `app/interfaces/routers/encounters.py` exposes POST `/encounters` (201), GET `/encounters/{encounter_id}` (200/404), GET `/patients/{patient_id}/encounters` (200/404).
  - [ ] Router imports ONLY from `app.usecases.*` and `app.interfaces.*`. `grep -nE '^from app\.infrastructure' encounters.py` → 0 hits.
  - [ ] `EncounterCreate` has `model_config = ConfigDict(extra='forbid')`.
  - [ ] PHI: no PHI in log lines; audit `meta_json="{}"` (no patient_id); error messages do not echo UUIDs.
  - [ ] Unit tests in `tests/usecases/test_encounter.py` and `tests/interfaces/test_encounters_router.py`.
  - [ ] Mounted in `main.py` via `app.include_router(encounters_router, prefix="")`.
- **Out-of-scope:** Encounter update/delete, pagination, search by date range, clinician existence validation, record draft/final endpoints.
- **Open-questions:** _(none)_
- **Inference Impact:** no
- **Data Sensitivity:** PHI; encounter linkage to a patient is PHI per `.claude/rules/local-llm-and-phi.md` §3. Mask before logger; never echo any UUID in error envelopes; audit `meta_json` stays `"{}"`.
- **Gates Touched:** G1, G2, G3, G4, G6, G7
- **Affected Layers:** usecases (extend), interfaces (new router)
- **Status:** done
