# Backend TASKS

Active task list for the backend. Each task is a Block per `docs/handoff-contract.md`. Generator owns this file (per `AGENTS.md` §3); Planner seeds initial tasks.

## How to add a task

1. Copy the Sample Task Block below; rename `## Sample: …` to `## <Feature title>`.
2. Fill every required field. `Open-questions` MUST be `_(none)_` before handoff.
3. Add a row to the Task Index. Use status values: `pending`, `in-progress`, `qa`, `done`, `blocked`.
4. On Evaluator pass, flip the row to `done`. Do not delete completed Blocks; they are the implementation log.

## Task Index

| ID      | Title                         | Status  | Gates Touched              | Owner     |
| ------- | ----------------------------- | ------- | -------------------------- | --------- |
| INF-001 | Runtime Topology              | done    | G0                         | Generator |
| BE-001  | Inference Adapter             | done    | G1, G2, G3, G4, G5, G7     | Generator |
| BE-002  | Persistence                   | done    | G1, G2, G3, G4, G6, G7     | Generator |
| BE-003  | API Surface                   | done    | G1, G2, G3, G4, G6, G7     | Generator |
| BE-004  | Patient endpoints             | done    | G1, G2, G3, G4, G6, G7     | Generator |
| BE-005  | Encounter endpoints           | done    | G1, G2, G3, G4, G6, G7     | Generator |
| BE-006  | Record Draft generation       | done    | G1, G2, G3, G4, G5, G6, G7 | Generator |
| BE-007  | Draft edit and finalize       | done    | G1, G2, G3, G4, G6, G7     | Generator |
| INF-002 | Integration gap fixes         | done    | G0, G1, G2, G3, G4, G6, G7 | Generator |
| BE-008  | Record Final correction chain | done    | G1, G2, G3, G4, G6, G7     | Generator |
| INF-003 | LLM memory budget alignment   | pending | G5 (primary), G6, G0       | Planner   |

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

---

## Draft edit and finalize (BE-007)

- **Goal:** Deliver the clinician-facing lifecycle endpoints after BE-006's AI draft generation. Three endpoints: PATCH `/drafts/{draft_id}` (edit draft, writes DRAFT_UPDATE audit), POST `/drafts/{draft_id}/finalize` (promote draft to immutable `record_final`, writes FINAL_CREATE audit, 409 if encounter already has a final), GET `/finals/{final_id}` (read a finalized record by id).
- **Inputs:**
  - backend/SPEC.md#api-surface — error envelope, response_model rule
  - backend/SPEC.md#layer-boundaries — DDD direction
  - backend/SPEC.md#persistence — RecordDraftRepository.update_content, RecordFinalRepository.add/find_by_id/find_by_encounter
  - SPEC.md#domain-glossary — record_draft, record_final, clinician
  - .claude/rules/local-llm-and-phi.md — draft/final content is PHI; mask before logger
  - backend/app/domain/entities.py — RecordDraft, RecordFinal, AuditAction.DRAFT_UPDATE, AuditAction.FINAL_CREATE
  - backend/app/infrastructure/db/repositories.py — repositories used
  - backend/app/usecases/di.py — DI seam extended
  - backend/app/usecases/errors.py — DraftNotFound already exists; FinalNotFound and EncounterAlreadyFinalized added
- **Acceptance:**
  - [x] edit_record_draft usecase in draft.py; DRAFT_UPDATE audit; DraftNotFound on miss
  - [x] finalize_draft_to_record_final and find_final_by_id in final.py; FINAL_CREATE audit; DraftNotFound/EncounterAlreadyFinalized on error
  - [x] FinalNotFound and EncounterAlreadyFinalized added to errors.py
  - [x] RecordFinalRepository.find_by_encounter added to repositories.py
  - [x] DI factories: make_edit_record_draft, make_finalize_draft_to_record_final, make_find_final_by_id
  - [x] PATCH /drafts/{draft_id} (200 DraftRead / 404 / 422); POST /drafts/{draft_id}/finalize (201 FinalRead / 404 / 409 / 422); GET /finals/{final_id} (200 FinalRead / 404)
  - [x] FinalRead schema in finals.py router; DraftEdit and FinalizeRequest in drafts.py router
  - [x] PHI never in logger calls; audit meta_json="{}"; error messages PHI-free
  - [x] Tests: usecases/test_draft.py (edit cases), usecases/test_final.py (new), interfaces/test_drafts_router.py (PATCH+finalize), interfaces/test_finals_router.py (new)
  - [x] G1 pyright 0 errors, G2 ruff clean, G3 pytest 160 pass
- **Out-of-scope:** Corrections/predecessor_id chain (BE-008). Listing drafts/finals. Auth. Soft delete. Frontend UI.
- **Open-questions:** _(none)_
- **Inference Impact:** no
- **Data Sensitivity:** PHI; draft/final content is free-text clinical narrative; masked before any logger call; never in error envelopes; never in audit meta.
- **Gates Touched:** G1, G2, G3, G4, G6, G7
- **Affected Layers:** usecases (extend), interfaces (extend drafts router + new finals router); infrastructure (add find_by_encounter to RecordFinalRepository)
- **Status:** done

---

## Record Draft generation (BE-006)

- **Goal:** Generate an AI-drafted medical record (SOAP-shaped plain text) for an existing encounter using `gemma4:e4b` via the existing `LocalLLMClient` Protocol, persist it as a `record_draft` row, write a `DRAFT_CREATE` audit row, and return it. Also expose a read endpoint for fetching a draft by id. Two endpoints: POST `/encounters/{encounter_id}/drafts`, GET `/drafts/{draft_id}`.
- **Inputs:**
  - SPEC.md#inference-layer-contract — `LocalLLMClient.generate(prompt, params)`; timeout 60 s; raises `InferenceError` on non-200/timeout with masked context.
  - SPEC.md#hardware-assumptions — first-token p95 ≤1 s; total p95 ≤6 s for 1k output tokens; VRAM peak ≤6 GB at Q4_0.
  - backend/SPEC.md#inference-adapter — `app/infrastructure/llm/` is the only layer that talks to the LLM; `FakeLocalLLMClient` is the default in unit tests.
  - backend/SPEC.md#layer-boundaries — DDD direction; router talks to usecase-DI seam only.
  - backend/SPEC.md#persistence — `RecordDraftRepository.add/find_by_id`, `EncounterRepository.find_by_id`, `AuditLogRepository.append(AuditAction.DRAFT_CREATE, ...)`.
  - .claude/rules/local-llm-and-phi.md — clinical_input and draft.content are PHI; masked before logger; allowed in prompt body to local model only.
  - backend/app/domain/entities.py — `RecordDraft`, `AuditAction.DRAFT_CREATE`.
  - backend/app/infrastructure/llm/{client.py,types.py,fake_client.py,errors.py} — Protocol, `GenerateParams`, `GenerateResponse`, `InferenceError`.
  - backend/app/usecases/di.py — existing usecase-layer DI seam to extend.
  - backend/app/usecases/errors.py — `EncounterNotFound` already exists; add `DraftNotFound`.
  - backend/app/interfaces/routers/{patients.py,encounters.py} — patterns to follow for router shape, error translation, OpenAPI responses.
- **Acceptance:**
  - [x] **Prompt module.** `app/usecases/prompts.py` defines `build_draft_prompt(clinical_input: str) -> str`. Deterministic, no logs, no LLM call. DRAFT_SYSTEM_PROMPT constant. Japanese SOAP format.
  - [x] **Usecase.** `app/usecases/draft.py` exports `generate_record_draft` and `find_draft_by_id`. generate_record_draft: (1) verify encounter; (2) build prompt; (3) call llm.generate; (4) persist RecordDraft + AuditLog in same transaction; (5) return draft. InferenceError propagates.
  - [x] **Router-level inference error mapping.** `inference_error_handler` in `exception_handlers.py` maps InferenceError → 503 `inference_unavailable`. Registered in main.py before unhandled_exception_handler.
  - [x] **Router.** `app/interfaces/routers/drafts.py`: POST `/encounters/{encounter_id}/drafts` (201/404/503), GET `/drafts/{draft_id}` (200/404).
  - [x] **Pydantic models.** `DraftCreate` (clinical_input, min_length=1, extra=forbid), `DraftRead` (id, encounter_id, content, confidence, created_at, updated_at).
  - [x] **PHI handling.** No PHI in logger calls; audit meta_json="{}"; InferenceError propagated as-is.
  - [x] **Usecase-DI seam.** `make_generate_record_draft`, `make_find_draft_by_id`, `get_llm_client` in di.py. Singleton via `make_llm_client()` factory.
  - [x] **response_model=** on every endpoint with 404/503 error models.
  - [x] **Tests.** `tests/usecases/test_draft.py`, `tests/usecases/test_prompts.py`, `tests/interfaces/test_drafts_router.py`.
- **Out-of-scope:** Streaming endpoint; draft edit/update; regenerate as distinct action; draft approval; list drafts; confidence-pill UX.
- **Open-questions:** _(none)_
- **Inference Impact:** yes; model `gemma4:e4b`; prompt ≤4k tokens, output ≤1.5k tokens; timeout 60 s.
- **Data Sensitivity:** PHI; clinical_input and draft.content are PHI; masked before logger; allowed in prompt body to local model only.
- **Gates Touched:** G1, G2, G3, G4, G5, G6, G7
- **Affected Layers:** usecases (extend), interfaces (new router + extend exception_handlers)
- **Status:** done

---

## Integration gap fixes (INF-002)

- **Goal:** Fix three pre-existing backend integration gaps that blocked every browser-driven E2E test: (a) Alembic env.py now uses async engine so `alembic upgrade head` works with `postgresql+asyncpg://`; (b) all timestamp columns are TIMESTAMPTZ so tz-aware UTC datetimes persist correctly; (c) FastAPI CORS middleware allows the browser at `http://localhost:3000` to call the API on `http://localhost:8000`. Add integration test for the timezone round-trip and unit tests for CORS preflight.
- **Inputs:**
  - backend/SPEC.md#persistence — migrations and DB schema
  - backend/SPEC.md#api-surface — CORS as part of API surface
  - CLAUDE.md §2 Scope — local PoC, `allow_origins=["http://localhost:3000"]`
  - .claude/rules/local-llm-and-phi.md §1 — CORS must NOT broaden to `*`
  - backend/migrations/env.py — sync engine_from_config (broken for asyncpg)
  - backend/migrations/versions/0001_initial_schema.py — TIMESTAMP without timezone
  - backend/app/infrastructure/db/models.py — Mapped[datetime] without timezone=True
  - backend/main.py — no CORS middleware
- **Acceptance:**
  - [ ] backend/migrations/env.py uses async_engine_from_config + run_sync(do_run_migrations)
  - [ ] `docker compose exec backend alembic upgrade head` succeeds on fresh postgres
  - [ ] 0001_initial_schema.py uses TIMESTAMP(timezone=True) for all timestamp columns
  - [ ] backend/app/infrastructure/db/models.py uses DateTime(timezone=True) for all timestamp columns
  - [ ] backend/main.py has CORSMiddleware registered before routers; allow_origins=["http://localhost:3000"] only
  - [ ] tests/integration/test_postgres_writes.py: round-trip asserts tzinfo is not None on audit_log.at
  - [ ] tests/interfaces/test_cors.py: allowed origin preflight → 200 with correct header; disallowed origin → no ACAO header matching evil origin; simple GET with allowed origin → ACAO header present
  - [ ] G1 pyright 0 errors; G2 ruff clean; G3 pytest -q all pass (CORS unit tests included, integration test deselected)
- **Out-of-scope:** BE-008 correction chain, auth, rate limiting, CSP headers, psycopg2-binary dependency
- **Open-questions:** _(none)_
- **Inference Impact:** no
- **Data Sensitivity:** PHI; schema change touches PHI columns but no new PHI exposure; CORS does not bypass masking
- **Gates Touched:** G0, G1, G2, G3, G4, G6, G7
- **Affected Layers:** infrastructure (db models + migrations + alembic env), interfaces (CORS middleware in main.py)
- **Status:** done

---

## Record Final correction chain (BE-008)

- **Goal:** Add the clinical correction flow on top of BE-007's immutable record_final. Three new endpoints + legacy cleanup. BE-007's `finalize_draft_to_record_final` semantics are unchanged.
- **Inputs:**
  - backend/SPEC.md#persistence — record_final immutable; corrections are new rows referencing predecessors
  - backend/SPEC.md#api-surface — error envelope, response_model rule
  - backend/SPEC.md#layer-boundaries — DDD direction (router → usecase-DI seam → infra → domain)
  - SPEC.md#domain-glossary — `record_final` 確定カルテ, `predecessor_id` for correction lineage
  - .claude/rules/local-llm-and-phi.md §3 — content is PHI; mask in logs; no PHI in error envelopes
  - backend/app/domain/entities.py — `RecordFinal.predecessor_id: UUID | None`; `AuditAction.FINAL_CORRECT`
  - backend/app/infrastructure/db/repositories.py — `RecordFinalRepository`
  - backend/app/usecases/final.py (BE-007) — extended with correction usecases
  - backend/app/usecases/record_finalization.py (legacy) — removed; superseded by BE-007 + BE-008
  - backend/app/interfaces/routers/finals.py (BE-007) — extended with POST correct + GET chain
- **Acceptance:**
  - [x] `correct_record_final` usecase: loads source, builds new RecordFinal(predecessor_id=source.id, confidence=None), adds to repo, writes FINAL_CORRECT audit with meta_json="{}"
  - [x] `list_finals_by_encounter` usecase: returns full list ordered by created_at ASC; empty list on no finals
  - [x] `find_chain_for_final` usecase: wraps find_chain; raises FinalNotFound if empty
  - [x] `RecordFinalRepository.list_by_encounter` added; find_by_encounter (BE-007 guard) unchanged
  - [x] DI: `make_correct_record_final`, `make_list_finals_by_encounter`, `make_find_chain_for_final` in di.py
  - [x] POST `/finals/{final_id}/correct` — 201 FinalRead; 404 final_not_found; 422 on empty/extra
  - [x] GET `/finals/{final_id}/chain` — list[FinalRead] oldest→newest; 404 on missing
  - [x] GET `/encounters/{encounter_id}/finals` — list[FinalRead] created_at ASC; 200 empty on no finals or unknown encounter
  - [x] Layer rule: `grep -RnE '^from app\.infrastructure' backend/app/interfaces/routers/{finals.py,encounters.py}` → 0 hits
  - [x] Legacy `record_finalization.py` and `test_record_finalization.py` removed; 0 references remain
  - [x] All logger calls log UUIDs only — no content logged; meta_json="{}" for FINAL_CORRECT
  - [x] Tests: usecases/test_final.py, interfaces/test_finals_router.py, interfaces/test_encounters_router.py extended
  - [x] G1 pyright 0 errors, G2 ruff clean, G3 pytest 184 pass (24 new tests)
- **Out-of-scope:** Frontend correction UI, auth/authorization, soft-delete of superseded finals, cross-encounter merging, confidence recomputation on correction
- **Open-questions:** _(none)_
- **Inference Impact:** no
- **Data Sensitivity:** PHI; `content` is free-text clinical narrative; masked before any logger call; never in error envelopes; `meta_json="{}"` for FINAL_CORRECT (predecessor lives on the row)
- **Gates Touched:** G1, G2, G3, G4, G6, G7
- **Affected Layers:** usecases (extend), interfaces (extend finals + encounters routers); infrastructure (one read-only method on RecordFinalRepository)
- **Status:** done

---

## LLM memory budget alignment (INF-003)

- **Goal:** Reconcile the gap between `SPEC.md#hardware-assumptions` ("VRAM peak ≤6 GB at gemma4:e4b Q4_0") and the observed runtime requirement of the actual `gemma4:e4b` Ollama tag, which loads ~9.8 GiB of system memory (9.4 GiB weights + 224 MiB KV cache + 125 MiB compute graph). On a Docker Desktop default (~5.7 GiB for the `llm` container) this prevents the model from loading, causing the inference endpoint to return 503 even when all earlier integration gaps are fixed. The mismatch was first observed during the FE-003 happy-path re-verification on 2026-05-11 (post-INF-002).
- **Inputs:**
  - SPEC.md#hardware-assumptions — VRAM peak ≤6 GB at Q4_0; 16 GB RAM reference
  - SPEC.md#inference-layer-contract — model `gemma4:e4b` is pinned; switching the variant requires an ADR
  - docker-compose.yml — `llm` service has no memory limit overrides; inherits Docker Desktop allocation
  - llm container log (2026-05-11): `model requires more system memory (9.8 GiB) than is available (5.7 GiB)`
  - Ollama manifest for `gemma4:e4b`: main blob `4c27e0f5b5ad` ≈ 9.6 GB (not Q4_0 quantization)
- **Acceptance (one of these paths, decided by Planner):**
  - [ ] **Path A — raise Docker memory limit:** docs/runbook-local-dev.md gains an explicit "Docker Desktop ≥ 12 GB RAM for the llm container" prerequisite; SPEC.md#hardware-assumptions is updated from "VRAM peak ≤6 GB at Q4_0" to the observed ~10 GiB system memory footprint. No code change, but the SPEC line is no longer false.
  - [ ] **Path B — switch to a smaller Ollama tag:** ADR opened (docs/adr/NNNN-*.md) accepting the model-tier change; SPEC.md#inference-layer-contract updates the pinned tag (candidate: `gemma3:4b` ≈ 2.5 GB Q4, or `gemma4:e4b-q4_0` if the publisher provides it); `frontend/src/lib/constants.ts` `LLM_MODEL` follows; `backend/app/infrastructure/llm/config.py` default follows.
  - [ ] **Path C — quantize locally:** Use Ollama's `ollama create` with a Modelfile that explicitly requests Q4_0 quantization off `gemma4:e4b`; SPEC line stays as-is. Adds a manual setup step to the runbook.
  - [ ] After whichever path: `curl POST /encounters/{id}/drafts` against a seeded encounter completes with 201 + AI draft text, AIIndicatedText renders the response in `/encounters/[id]/draft`, and the FE-003 happy path is observable end-to-end via Playwright MCP from the main loop.
- **Out-of-scope:** Multi-model routing; embeddings; cross-tag fallback chains.
- **Open-questions:** Which path? Planner decides based on the team's compute envelope and how strict the "Q4_0 ≤6 GB" SPEC line should be treated.
- **Inference Impact:** yes; this is a model-tier / memory budget reconciliation, the canonical G5 concern.
- **Data Sensitivity:** none for this Block (no PHI surface change).
- **Gates Touched:** G5 (primary), G6 (SPEC alignment), G0 (compose / runbook).
- **Affected Layers:** infrastructure (llm config + docker-compose if memory limits added); docs (runbook + SPEC.md update).
- **Status:** pending
