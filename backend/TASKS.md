# Backend TASKS

Active task list for the backend. Each task is a Block per `docs/handoff-contract.md`. Generator owns this file (per `AGENTS.md` §3); Planner seeds initial tasks.

## How to add a task

1. Copy the Sample Task Block below; rename `## Sample: …` to `## <Feature title>`.
2. Fill every required field. `Open-questions` MUST be `_(none)_` before handoff.
3. Add a row to the Task Index. Use status values: `pending`, `in-progress`, `qa`, `done`, `blocked`.
4. On Evaluator pass, flip the row to `done`. Do not delete completed Blocks; they are the implementation log.

## Task Index

| ID      | Title                                       | Status | Gates Touched                  | Owner     |
| ------- | ------------------------------------------- | ------ | ------------------------------ | --------- |
| INF-001 | Runtime Topology                            | done   | G0                             | Generator |
| BE-001  | Inference Adapter                           | done   | G1, G2, G3, G4, G5, G7         | Generator |
| BE-002  | Persistence                                 | done   | G1, G2, G3, G4, G6, G7         | Generator |
| BE-003  | API Surface                                 | done   | G1, G2, G3, G4, G6, G7         | Generator |
| BE-004  | Patient endpoints                           | done   | G1, G2, G3, G4, G6, G7         | Generator |
| BE-005  | Encounter endpoints                         | done   | G1, G2, G3, G4, G6, G7         | Generator |
| BE-006  | Record Draft generation                     | done   | G1, G2, G3, G4, G5, G6, G7     | Generator |
| BE-007  | Draft edit and finalize                     | done   | G1, G2, G3, G4, G6, G7         | Generator |
| INF-002 | Integration gap fixes                       | done   | G0, G1, G2, G3, G4, G6, G7     | Generator |
| BE-008  | Record Final correction chain               | done   | G1, G2, G3, G4, G6, G7         | Generator |
| INF-003 | LLM memory budget alignment                 | done   | G5 (primary), G6, G0           | Planner   |
| BE-009  | List drafts for encounter                   | done   | G1, G2, G3, G4, G6, G7         | Generator |
| BE-010  | Security hardening bundle                   | done   | G1, G2, G3, G4, G6, G7         | Generator |
| BE-011  | INFO-level UUID hardening sweep             | done   | G1, G2, G3, G4, G6, G7         | Generator |
| BE-012  | X-Clinician-Id header auth                  | done   | G1, G2, G3, G4, G6, G7         | Generator |
| BE-013  | Streaming draft endpoint                    | done   | G1, G2, G3, G4, G5, G6, G7     | Generator |
| INF-004 | ASR compose service                         | done   | G0, G4, G5, G6, G7             | Generator |
| BE-014  | ASR adapter + transcribe endpoint           | done   | G0, G1, G2, G3, G4, G5, G6, G7 | Generator |
| BE-015  | Hardening ADVICE bundle                     | done   | G1, G2, G3, G4                 | Generator |
| BE-016  | Backend ffmpeg transcode + ASR error gating | done   | G0, G1, G2, G3, G4, G5         | Generator |
| BE-017  | Streaming transcribe endpoint               | done   | G1, G2, G3, G4, G5, G6, G7     | Generator |

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
- **Acceptance — Path A selected (2026-05-11) and applied:**
  - [x] **Path A — raise Docker memory limit:** `docs/runbook-local-dev.md` Prerequisites updated to "Docker Desktop ≥ 12 GB RAM for the llm container" with explicit settings-screen pointer; "System RAM: 24 GB recommended" added matching SPEC reference hardware. `SPEC.md#hardware-assumptions` re-authored by Planner: the "VRAM peak ≤6 GB at Q4_0" line is gone; replaced by the observed ~10 GiB system-memory footprint at the publisher-supplied default precision, plus the parenthetical that Q4_0 re-quantization is out-of-scope.
  - [ ] Path B (switch tag) — not chosen.
  - [ ] Path C (Modelfile re-quantize) — not chosen.
  - [ ] After Path A landed: `curl POST /encounters/{id}/drafts` happy path is unblocked as soon as the developer raises Docker memory; Playwright happy-path re-verification of FE-003/004/005 deferred to a separate task tracked in the pending list (interactive flows; not gating INF-003 itself).
- **Out-of-scope:** Multi-model routing; embeddings; cross-tag fallback chains; the Playwright happy-path re-runs (tracked separately).
- **Open-questions:** _(none — Path A chosen on 2026-05-11)_
- **Inference Impact:** yes; this is a model-tier / memory budget reconciliation, the canonical G5 concern.
- **Data Sensitivity:** none for this Block (no PHI surface change).
- **Gates Touched:** G5 (primary), G6 (SPEC alignment), G0 (compose / runbook).
- **Affected Layers:** infrastructure (no code change in Path A); docs (runbook + SPEC.md).
- **Status:** done

---

## List drafts for encounter (BE-009)

- **Goal:** Add `GET /encounters/{encounter_id}/drafts` returning `list[DraftRead]` ordered by `created_at` DESC (newest first). Frontend can pick the head for resume / auto-load. Empty list on encounter with no drafts. Consistent with BE-008's `GET /encounters/{id}/finals` shape.
- **Inputs:**
  - backend/SPEC.md#api-surface — error envelope, response_model rule
  - backend/SPEC.md#persistence — RecordDraftRepository pattern
  - backend/SPEC.md#layer-boundaries — DDD direction
  - SPEC.md#domain-glossary — `record_draft`
  - .claude/rules/local-llm-and-phi.md §3, §4 — content is PHI; operational read returns PHI fields
  - backend/app/infrastructure/db/repositories.py — `RecordDraftRepository`
  - backend/app/usecases/di.py — usecase-DI seam to extend
  - backend/app/usecases/draft.py — to extend with the list usecase
  - backend/app/interfaces/routers/encounters.py — pattern to follow
- **Acceptance:**
  - [ ] `RecordDraftRepository.list_by_encounter(encounter_id: UUID) -> list[RecordDraft]` added; `SELECT ... WHERE encounter_id = $1 ORDER BY created_at DESC`; logs UUID only.
  - [ ] `list_drafts_by_encounter(encounter_id: UUID, ...) -> list[RecordDraft]` added to `app/usecases/draft.py`; empty list is valid; no encounter-existence check; logs UUID + count only.
  - [ ] `make_list_drafts_by_encounter` factory added to `app/usecases/di.py`.
  - [ ] `GET /encounters/{encounter_id}/drafts` added to `app/interfaces/routers/encounters.py`; `response_model=list[DraftRead]`; 200 empty list on unknown encounter.
  - [ ] `grep -RnE '^from app\.infrastructure' backend/app/interfaces/routers/encounters.py` → 0 hits.
  - [ ] `DraftRead` imported from `app.interfaces.routers.drafts`.
  - [ ] `tests/usecases/test_draft.py` extended: list with N drafts ordered DESC; empty list; no encounter-existence check.
  - [ ] `tests/interfaces/test_encounters_router.py` extended with `TestGetDraftsByEncounter`: 200 one draft; 200 multiple drafts newest-first; 200 empty on unknown encounter.
- **Out-of-scope:** "Latest draft only" sugar endpoint, patient-scoped draft search, pagination, soft delete, auth gating.
- **Open-questions:** _(none)_
- **Inference Impact:** no
- **Data Sensitivity:** PHI; `content` returned in response body is the operational-read path per `.claude/rules/local-llm-and-phi.md` §4; no logger calls log content; error envelopes generic.
- **Gates Touched:** G1, G2, G3, G4, G6, G7
- **Affected Layers:** infrastructure (repository +list_by_encounter), usecases (extend draft.py +di.py), interfaces (extend encounters router)
- **Status:** done

---

## Security hardening bundle (BE-010)

- **Goal:** Tighten four PHI-leak vectors flagged as ADVICE in prior security-check reports. Pure defensive hardening — no new endpoints, no schema change, no behavioural drift on success paths.
- **Inputs:**
  - .claude/rules/local-llm-and-phi.md §3 §4 — PHI in prompts/logs; operational reads
  - backend/SPEC.md#api-surface — error envelope
  - Prior security-check reports (BE-003, BE-005, BE-006, FE-002)
- **Acceptance:**
  - [ ] Item 1: `http_exception_handler` always masks string detail via `mask_phi`, regardless of length. The `len > 64` threshold is removed. `grep -nE 'len\(.*\)\s*>\s*64' backend/app/interfaces/exception_handlers.py` returns 0 hits.
  - [ ] Item 1 test: `test_exception_handlers.py` includes a test for short PHI-containing detail that confirms the response message is masked.
  - [ ] Item 2: `unhandled_exception_handler` logs only `exc.__class__.__module__ + "." + exc.__class__.__name__` + top-frame file:line. No `traceback.format_exc()` in production code. `grep -RnE 'traceback\.format_exc\(\)' backend/app` returns 0 hits.
  - [ ] Item 2 test: `test_exception_handlers.py` uses `caplog` to assert the logged line contains the redacted class+location and does NOT contain the raw exception message or user input.
  - [ ] Item 3: All `logger.debug(...)` lines in `backend/app/usecases/**` that interpolate a UUID use `short_id(uuid)` helper. `short_id` is defined in `app/domain/phi.py` and returns the first 8 hex chars + `…`.
  - [ ] Item 3 test: `app/domain/phi.py` tests cover `short_id` for empty / typical UUID / non-UUID string.
  - [ ] Item 4: `_buildServerErrorContext` and its `void` call site are deleted from `frontend/src/lib/api.ts`. `grep -rn '_buildServerErrorContext' frontend/src` returns 0 hits.
  - [ ] Item 4 verification: existing 21+ tests in `frontend/src/services/__tests__/drafts.test.ts` and `frontend/src/lib/__tests__/maskPhi.test.ts` remain green.
- **Out-of-scope:** Auth/authorization. Streaming UI. New endpoints. Schema migrations. Success-path response shape changes. PHI rule amendments.
- **Open-questions:** _(none)_
- **Inference Impact:** no
- **Data Sensitivity:** PHI (defensive hardening of existing PHI surfaces — no new exposure introduced)
- **Gates Touched:** G1, G2, G3, G4, G6, G7
- **Affected Layers:** interfaces (exception_handlers), usecases (DEBUG log hardening), domain (short_id helper), frontend lib (api.ts)
- **Status:** done

---

## INFO-level UUID hardening sweep (BE-011)

- **Goal:** Replace bare UUID interpolation with `short_id(...)` at all remaining INFO-level call sites in usecases. Defence-in-depth: UUIDs are not enumerated PHI under `.claude/rules/local-llm-and-phi.md` §3, but shortening them reduces re-identification risk if logs are scraped from a stolen device and achieves consistent log shape across DEBUG/INFO levels.
- **Inputs:**
  - .claude/rules/local-llm-and-phi.md §3
  - backend/app/domain/phi.py — `short_id` helper from BE-010
  - BE-010 security-check ADVICE: INFO-level lines in `draft.py:107`, `draft.py:188`, `final.py:96-101`, `final.py:172-177`, `encounter.py:74`, `patient.py:72` still interpolated full UUIDs
- **Acceptance:**
  - [x] `encounter.py:74` — `encounter.id` wrapped: `short_id(encounter.id)`
  - [x] `draft.py:107` — `draft.id`, `encounter_id` both wrapped with `short_id(...)`
  - [x] `draft.py:188` — `draft_id`, `clinician_id` both wrapped with `short_id(...)`
  - [x] `final.py:96-101` — `final.id`, `draft_id`, `clinician_id` all wrapped with `short_id(...)`
  - [x] `final.py:172-177` — `new_final.id`, `source_final_id`, `clinician_id` all wrapped with `short_id(...)`
  - [x] `patient.py:72` — `patient.id` wrapped: `short_id(patient.id)`
  - [x] `grep -nE 'logger\.(info|warning)\(.*%s.*,\s*[a-z_]+_id\b' backend/app/usecases` — all remaining hits already use `short_id(...)`
  - [x] `logger.error(...)` sites unchanged — incident correlation retains full UUIDs (none found in usecases)
  - [x] audit_log `meta_json="{}"` unchanged at all sites
  - [x] No behaviour change; G3 pytest 208 passed baseline maintained
  - [x] `short_id` signature unchanged from BE-010
- **Out-of-scope:** ERROR-level UUID logging; audit_log meta_json; `short_id` helper changes; non-usecase modules.
- **Open-questions:** _(none)_
- **Inference Impact:** no
- **Data Sensitivity:** PHI (hardening — no new exposure introduced)
- **Gates Touched:** G1, G2, G3, G4, G6, G7
- **Affected Layers:** usecases only (INFO logging hardening)
- **Status:** done

---

## X-Clinician-Id header auth (BE-012)

- **Goal:** Introduce a lightweight header-trust auth dependency (`get_current_clinician`) that extracts a clinician UUID from the `X-Clinician-Id` request header, wires it into all PHI-returning endpoints, removes `clinician_id` from request bodies, removes `_PLACEHOLDER_CLINICIAN_ID` from usecases, and threads the real clinician UUID through the audit log chain. Frontend sends the header on every `apiFetch` call from a PoC constant.
- **Inputs:**
  - backend/SPEC.md#api-surface — 401 envelope, header-trust pattern
  - backend/SPEC.md#layer-boundaries — DDD direction; auth in `interfaces/` only
  - .claude/rules/local-llm-and-phi.md §3, §4 — PHI in logs/errors
  - backend/app/interfaces/routers/{patients,encounters,drafts,finals}.py — all PHI-returning routers
  - backend/app/usecases/{patient,draft,final}.py — placeholder removal
  - backend/app/usecases/di.py — DI callable types
  - frontend/src/lib/{api.ts,constants.ts} — header injection
- **Acceptance:**
  - [x] `app/interfaces/auth.py` exports `get_current_clinician` FastAPI dependency; returns `UUID`; raises 401 `{code: "unauthenticated", message: "Clinician identification required."}` on missing/malformed header
  - [x] `get_current_clinician` does NOT import from `app.usecases` or `app.infrastructure`
  - [x] All PHI-returning endpoints in `patients.py`, `encounters.py`, `drafts.py`, `finals.py` depend on `get_current_clinician`
  - [x] `clinician_id` removed from `EncounterCreate`, `DraftEdit`, `FinalizeRequest`, `FinalCorrectRequest` request bodies; sending it returns 422
  - [x] `_PLACEHOLDER_CLINICIAN_ID` removed from `patient.py`, `draft.py`, `final.py`
  - [x] `create_patient` and `generate_record_draft` usecases accept `clinician_id: UUID` parameter; audit logs use the real clinician ID
  - [x] DI callables `CreatePatientCallable` and `GenerateRecordDraftCallable` updated to include `clinician_id`
  - [x] `tests/conftest.py` provides `TEST_CLINICIAN_ID` and `auth_headers` fixture
  - [x] `tests/interfaces/test_auth.py` has ≥4 tests: missing header → 401, malformed → 401, valid → passes through, envelope shape correct
  - [x] All existing router tests updated: `get_current_clinician` overridden; body payloads without `clinician_id`
  - [x] All usecase unit tests updated: `clinician_id=uuid4()` passed directly
  - [x] `frontend/src/lib/constants.ts` exports `CLINICIAN_ID = "00000000-0000-0000-0000-0000000a11ce"`
  - [x] `frontend/src/lib/api.ts` `apiFetch` sends `X-Clinician-Id: CLINICIAN_ID` on every request; never written to storage
  - [x] G1 pyright 0 errors, G2 ruff clean, G3 pytest all pass
- **Out-of-scope:** Signature verification, JWT, session management, clinician existence check in DB, RBAC, frontend login UI.
- **Open-questions:** _(none)_
- **Inference Impact:** no
- **Data Sensitivity:** PHI; clinician UUID is an actor identifier; not echoed in error messages; not logged raw
- **Gates Touched:** G1, G2, G3, G4, G6, G7
- **Affected Layers:** interfaces (new auth.py, all 4 routers), usecases (patient.py, draft.py, final.py, di.py), frontend (api.ts, constants.ts)
- **Status:** done

---

## Streaming draft endpoint (BE-013)

- **Goal:** Add `POST /encounters/{encounter_id}/drafts/stream` returning an SSE stream. Validates the encounter, streams chunks from `LocalLLMClient.stream()`, encodes each as an SSE event, then after the stream completes persists the assembled draft and a `DRAFT_CREATE` audit row (mirroring BE-006's non-stream path).
- **Inputs:**
  - SPEC.md#inference-layer-contract — `LocalLLMClient.stream(prompt, params) -> AsyncIterator[Chunk]`; 120 s end-to-end timeout; raises `InferenceError` with masked context on failure.
  - backend/SPEC.md#api-surface — error envelope `{code, message}`; `response_model=`.
  - backend/app/infrastructure/llm/types.py — `Chunk(text: str, done: bool, confidence: float | None)`.
  - backend/app/infrastructure/llm/{ollama_client.py, fake_client.py} — both implement `.stream()`.
  - backend/app/usecases/draft.py (BE-006) — `generate_record_draft` to mirror.
  - backend/app/usecases/prompts.py — `build_draft_prompt(clinical_input)`.
  - backend/app/usecases/di.py — `get_llm_client` factory.
  - backend/app/interfaces/auth.py — `get_current_clinician` dependency.
  - backend/app/interfaces/exception_handlers.py — `inference_error_handler` for 503 mapping.
  - backend/app/infrastructure/db/repositories.py — `RecordDraftRepository.add`, `EncounterRepository.find_by_id`, `AuditLogRepository.append`.
  - .claude/rules/local-llm-and-phi.md §3 — clinical_input + chunk.text + assembled draft.content are PHI; mask before logger.
- **Acceptance:**
  - [ ] New `stream_record_draft` async generator in `app/usecases/draft.py` yielding `Chunk`; after stream completes persists draft + DRAFT_CREATE audit; yields one final completion chunk carrying the new draft id.
  - [ ] On `InferenceError` mid-stream, nothing persisted; exception propagates.
  - [ ] On `EncounterNotFound`, raises before any LLM call (router maps to synchronous 404).
  - [ ] Logger discipline: short_id for encounter/clinician; never log clinical_input, chunk.text, or content.
  - [ ] New endpoint `POST /encounters/{encounter_id}/drafts/stream` in `app/interfaces/routers/drafts.py`; `StreamingResponse` with `media_type="text/event-stream"`.
  - [ ] SSE format: `data: {...}\n\n` for chunks; `event: complete\ndata: {...}\n\n` for completion; `event: error\ndata: {...}\n\n` for mid-stream errors.
  - [ ] 404/422 happen synchronously (before stream opens); InferenceError mid-stream becomes SSE error event.
  - [ ] `grep -nE '^from app\.infrastructure' backend/app/interfaces/routers/drafts.py` → 0 hits.
  - [ ] `make_stream_record_draft` factory in `app/usecases/di.py` mirroring `make_generate_record_draft`.
  - [ ] Usecase tests: stream happy path; missing encounter; InferenceError mid-stream (no persist).
  - [ ] Router tests: 200 SSE frames; 404 synchronous; 422 synchronous; InferenceError mid-stream SSE error event.
  - [ ] Non-stream endpoint tests unchanged.
- **Out-of-scope:** Resumable streams; multi-client concurrent streams; WebSocket/WebTransport; editing/finalizing via stream.
- **Open-questions:** _(none)_
- **Inference Impact:** yes; stream path; model `gemma4:e4b`; prompt ≤4k tokens, output ≤1.5k tokens; 120 s end-to-end timeout; system-memory footprint ~10 GiB (publisher-supplied default precision, post-INF-003); Docker memory floor ≥13 GiB (post-INF-004, co-resident with whisper.cpp medium-q5_0).
- **Data Sensitivity:** PHI; clinical_input and chunk.text are PHI; never echoed in logger or SSE error frames.
- **Gates Touched:** G1, G2, G3, G4, G5, G6, G7
- **Affected Layers:** usecases (extend draft.py + di.py), interfaces (extend drafts router)
- **Status:** done

---

## ASR Compose Service (INF-004)

- **Goal:** Internal-only `asr` Docker Compose service built from `docker/asr/Dockerfile` (whisper.cpp v1.7.5 source build, GGML_NATIVE=OFF for arm64/amd64 portability) running `whisper-server` with the `medium-q5_0` GGML model, raise the Docker memory floor in the runbook, and prime ASR env-vars on the backend service. No Python/TS code lands in this Block. Source build is engineering-equivalent to the ADR's `ghcr.io/ggml-org/whisper.cpp:main` reference — the prebuilt is amd64-only and hangs under Rosetta 2 on Apple Silicon (reproduced 2026-05-12).
- **Inputs:**
  - SPEC.md#asr-layer-contract — service endpoint, env var names
  - SPEC.md#hardware-assumptions — Docker memory floor ≥13 GB
  - docs/adr/0001-voice-input-and-local-asr.md — variant pick (medium-q5_0), port (8080), network boundary; ADR pins binary + port + license, not the GHCR delivery path
  - .claude/rules/local-llm-and-phi.md §1 §3 — no host ports for asr; audio = PHI
  - docker-compose.yml — existing service shape to follow
  - docker/asr/Dockerfile — source build: ARG WHISPER_VERSION=v1.7.5; cmake GGML_NATIVE=OFF; multi-stage debian:bookworm-slim
  - docs/runbook-local-dev.md — runbook to update
- **Acceptance:**
  - [ ] `docker-compose.yml` defines `asr` service using `build: { context: ./docker/asr }` (source build from `docker/asr/Dockerfile`; whisper.cpp v1.7.5 pinned via `ARG WHISPER_VERSION`; GGML_NATIVE=OFF for arm64/amd64 portability).
  - [ ] `asr` service joins `internal` network only; no `ports:` entry.
  - [ ] `asr` service volume `asr_data:/models` persists GGML weights across container recreation.
  - [ ] `asr` startup command: download `ggml-medium-q5_0.bin` into `/models` if absent, then exec `whisper-server` with `--host 0.0.0.0 --port 8080 -m /models/ggml-medium-q5_0.bin`.
  - [ ] Healthcheck: TCP port-open check on 8080 (no full transcription); `start_period: 120s`.
  - [ ] `backend` service gains env vars: `ASR_BASE_URL=http://asr:8080`, `ASR_MODEL=ggml-medium-q5_0.bin`, `ASR_TIMEOUT_S=90`.
  - [ ] Top-level `volumes:` block adds `asr_data:` alongside `postgres_data` and `ollama_data`.
  - [ ] `docs/runbook-local-dev.md` updated: Docker Desktop memory ≥12 GB → ≥13 GB; topology diagram adds `asr`; first-boot section notes ~0.7 GiB additional model pull.
  - [ ] `backend/TASKS.md` INF-004 row status: `in-progress` → `qa` on Generator self-eval green.
  - [ ] G0: `docker compose ps --status running` shows 5 services healthy.
  - [ ] G4: `grep -E 'asr.*\bports:' docker-compose.yml` → 0 hits; `grep -E 'extra_hosts|host.docker.internal' docker-compose.yml` → 0 hits.
  - [ ] G6/G7: `grep -RE 'http://asr[: ]|whisper' backend/app` → 0 hits (no backend code touches ASR yet).
- **Out-of-scope:** `app/infrastructure/asr/` Python code (BE-014); `/encounters/{id}/transcribe` endpoint (BE-014); `RecordButton` atom / `VoiceCapture` molecule (FE-009); adding `asr` to `/health` (BE-014 scope).
- **Open-questions:** _(none)_
- **Inference Impact:** yes; whisper.cpp medium-q5_0; ASR_TIMEOUT_S=90; co-resident with gemma4:e4b; total Docker memory budget ≈13 GiB.
- **Data Sensitivity:** PHI; audio = PHI per ADR-0001 + rule §3; no PHI flows in this Block (compose-only, no audio processed).
- **Gates Touched:** G0, G4, G5, G6, G7
- **Affected Layers:** infrastructure (compose only), docs/runbook
- **Status:** qa

---

## ASR Adapter and Transcribe Endpoint (BE-014)

- **Goal:** Implement `POST /encounters/{encounter_id}/transcribe` end-to-end: `LocalASRClient` Protocol + `WhisperCppLocalASRClient` concrete + `FakeLocalASRClient` test double under `app/infrastructure/asr/`, `transcribe_audio` usecase, DI factory, router, and full unit tests. Audio = PHI; never logged, never persisted.
- **Inputs:**
  - backend/SPEC.md#asr-adapter
  - backend/SPEC.md#transcribe-endpoint
  - SPEC.md#asr-layer-contract
  - docs/adr/0001-voice-input-and-local-asr.md
  - .claude/rules/local-llm-and-phi.md §1 §2 §3
- **Acceptance:**
  - [x] `app/infrastructure/asr/__init__.py` exports `LocalASRClient`, `WhisperCppLocalASRClient`, `FakeLocalASRClient`, `ASRError`, `ASR_BASE_URL`, `ASR_MODEL`, `ASR_TIMEOUT_S`, `make_asr_client()`
  - [x] `app/infrastructure/asr/config.py` reads env vars with defaults (`http://asr:8080`, `ggml-medium-q5_0.bin`, `90`)
  - [x] `app/infrastructure/asr/client.py` defines `LocalASRClient` Protocol with `transcribe(audio, params) -> TranscribeResponse` and `ping() -> bool`
  - [x] `app/infrastructure/asr/whisper_cpp_client.py` POSTs multipart to `/inference`, raises `ASRError` on timeout/non-2xx/network error, does not log audio bytes
  - [x] `app/infrastructure/asr/fake_client.py` returns fixed synthetic Japanese string; fixture_map keyed by sha256(bytes)[:16]
  - [x] `app/infrastructure/asr/errors.py` `ASRError` with masked context; no audio bytes in `__str__`/`__repr__`
  - [x] `app/usecases/transcribe.py` `transcribe_audio(...)`: validates encounter, calls ASR, returns transcript. No DB writes, no audit rows.
  - [x] `app/usecases/di.py` adds `get_asr_client()`, `make_transcribe_audio()`, `TranscribeAudioCallable`
  - [x] `app/interfaces/routers/transcribe.py` `POST /encounters/{encounter_id}/transcribe`: multipart, 2MB cap, audio/webm content-type check, 503/504/404/415/422 error mapping
  - [x] `main.py` wires transcribe_router; health endpoint adds `asr` field; /health returns 200 iff postgres+llm+asr all reachable
  - [x] `python-multipart==0.0.20` added to requirements.txt (required for UploadFile/multipart)
  - [x] Tests: `tests/infrastructure/asr/test_whisper_cpp_client.py` (9 tests), `tests/infrastructure/asr/test_fake_client.py` (8 tests), `tests/usecases/test_transcribe.py` (5 tests), `tests/interfaces/test_transcribe_router.py` (9 tests); existing health tests updated to mock ASR ping
  - [x] Layer rule: `grep -RnE '^from app\.infrastructure\.asr' backend/app/interfaces/` → 0 hits
  - [x] G0 green: 5 services healthy; `/health` returns `{"status":"ok","postgres":true,"llm":true,"asr":true}`; `POST /encounters/unknown/transcribe` → 404 (endpoint live)
  - [x] G1 pyright 0 errors; G2 ruff clean; G3 pytest 266 passed (was 208; +58 new)
  - [x] G4 security: no hosted-ASR SDKs; no direct ASR calls outside infra; no audio in logs; no persistence; X-Clinician-Id required
  - [x] G5 cost: ASR_TIMEOUT_S=90; 2MB cap; no audio persistence; co-resident 13GiB budget in runbook
- **Out-of-scope:** Frontend (FE-009). Audio persistence / audit row. Streaming transcription. Multi-speaker / diarization. kotoba-whisper swap.
- **Open-questions:** _(none)_
- **Inference Impact:** yes; whisper.cpp medium-q5_0; ASR_TIMEOUT_S=90; co-resident with gemma4:e4b.
- **Data Sensitivity:** PHI; audio bytes and transcript are PHI; never logged at INFO; never persisted.
- **Gates Touched:** G0, G1, G2, G3, G4, G5, G6, G7
- **Affected Layers:** infrastructure (new asr/), usecases (transcribe.py + di.py), interfaces (new router, main.py health)
- **Status:** qa

---

## Hardening ADVICE bundle (BE-015)

- **Goal:** Address three accumulated defense-in-depth ADVICE items in one focused commit. None block functionality; all reduce PHI re-identification risk or doc drift.
- **Inputs:**
  - backend/app/domain/phi.py — `mask_phi` current implementation (short-value edge behavior)
  - backend/app/interfaces/exception_handlers.py — `unhandled_exception_handler` absolute container path
  - backend/TASKS.md — BE-013 Inference Impact field (stale hardware budget reference)
  - .claude/rules/local-llm-and-phi.md §3 — PHI in logs
  - BE-010 security-check ADVICE (mask_phi short-value preview)
  - BE-010 security-check ADVICE (5xx log container-absolute filename)
  - BE-013 cost-check ADVICE (SPEC reference drift on hardware budget)
- **Acceptance:**
  - [x] Item 1: `mask_phi` returns `"***"` for values ≤4 chars; values ≥5 chars retain existing preview behavior. `grep -nE 'preview_len = min' backend/app/domain/phi.py` → guarded by `len(value) <= 4` branch.
  - [x] Item 1 tests: `tests/domain/test_phi.py` has ≥3 new tests covering empty, 1-char, 4-char (→ `"***"`), 5-char (→ preview), 9-char (→ tail masked).
  - [x] Item 2: `unhandled_exception_handler` log uses `top_frame.filename.removeprefix("/app/")` — project-relative path only. `grep -n 'removeprefix' backend/app/interfaces/exception_handlers.py` → 1 hit.
  - [x] Item 2: existing `test_exception_handlers.py` tests for log format remain green (assert `.py:` still present).
  - [x] Item 3: BE-013 `Inference Impact` field updated to state budget explicitly (post-INF-003/INF-004 values) instead of deferring to stale BE-006 reference. No code change.
  - [x] G1 pyright — 0 errors
  - [x] G2 ruff check + ruff format --check — clean
  - [x] G3 pytest -q — all tests pass; ≥3 new mask_phi tests
  - [x] G4 security-check — PASS, no CRITICAL findings
- **Out-of-scope:** Frontend ADVICE items (FE-011). Refactoring mask_phi to SHA hash strategy. New log destinations. PHI rule §3 amendment.
- **Open-questions:** _(none)_
- **Inference Impact:** no
- **Data Sensitivity:** PHI (hardening of PHI log surfaces — no new exposure introduced)
- **Gates Touched:** G1, G2, G3, G4
- **Affected Layers:** domain (mask_phi), interfaces (exception_handlers), docs (TASKS.md)
- **Status:** qa

---

## Backend ffmpeg transcode + ASR error gating (BE-016)

- **Goal:** (a) Transcode `audio/webm;codecs=opus` (and any other non-WAV audio content-type) to 16 kHz mono PCM WAV in `WhisperCppLocalASRClient.transcribe()` before POSTing to whisper-server. (b) Detect empty transcript / decode-failure response and raise `ASRError` → 503 surfaced to frontend as `transcription_unavailable`. (c) Add ffmpeg to `backend/Dockerfile`. Restores the SPEC-intended user flow (record → upload → transcript) without rebuilding the ASR container.

  **ADR-0001 erratum:** ADR-0001 §Decision stated "Resample to 16 kHz happens server-side in whisper.cpp". This is incorrect for source-built whisper.cpp compiled without libavcodec (INF-004's `docker/asr/Dockerfile` does not link ffmpeg). The intent (local ASR transcription) is preserved; the implementation path moves the transcode step to the backend Python layer.

- **Inputs:**
  - backend/SPEC.md#asr-adapter
  - .claude/rules/local-llm-and-phi.md §3
  - docs/adr/0001-voice-input-and-local-asr.md
  - backend/app/infrastructure/asr/whisper_cpp_client.py (BE-014 implementation)
  - backend/Dockerfile
- **Acceptance:**
  - [x] `backend/Dockerfile` adds `apt-get install -y --no-install-recommends ffmpeg`
  - [x] `_transcode_to_wav(audio_bytes, source_mime)` private async function in `whisper_cpp_client.py`; pipes stdin → stdout via `asyncio.create_subprocess_exec`; no temp files; raises `ASRError` on non-zero exit or missing binary
  - [x] `audio/wav` short-circuit: `_transcode_to_wav` returns bytes unchanged when `source_mime.startswith("audio/wav")`
  - [x] `transcribe()` calls `_transcode_to_wav()` before building `files=` dict; sends `("audio.wav", wav_bytes, "audio/wav")` to whisper-server
  - [x] Empty-text gating: `{"text": ""}` or whitespace-only → `ASRError("transcribe returned empty text ...") → 503`
  - [x] Unit tests: WAV passthrough (2), transcode success, non-zero exit → ASRError, ffmpeg missing → ASRError; transcribe tests updated to mock `_transcode_to_wav`; empty-text gating; whitespace-text gating; WAV file sent to whisper
  - [x] G0 Dockerfile change; `docker compose build backend` required (documented)
  - [x] G1 pyright 0 errors
  - [x] G2 ruff clean
  - [x] G3 pytest 279 pass (was 271; +8 new tests)
  - [x] G4 security-check PASS: subprocess stderr captured-and-discarded (not logged); no temp files; no hosted-LLM SDKs; no direct ASR calls outside infra
  - [x] G5 cost-check PASS: ffmpeg transcode <2 s for 60 s/2 MB clip; ASR_TIMEOUT_S=90 provides headroom; image size delta ~80 MB (acceptable)
- **Out-of-scope:** Rebuilding whisper.cpp ASR image with libavcodec. Frontend changes. Streaming transcription. Audio persistence.
- **Open-questions:** _(none)_
- **Inference Impact:** yes; ASR path unchanged; whisper.cpp medium-q5_0; ASR_TIMEOUT_S=90
- **Data Sensitivity:** PHI; audio bytes in-memory only; subprocess piping; no disk writes
- **Gates Touched:** G0, G1, G2, G3, G4, G5
- **Affected Layers:** infrastructure (asr/whisper_cpp_client.py), docker (backend Dockerfile)
- **Status:** qa

---

## Streaming transcribe endpoint (BE-017)

- **Goal:** Add `POST /encounters/{encounter_id}/transcribe/stream` returning an SSE stream of progressive transcript chunks. Extends `LocalASRClient` Protocol with `stream_transcribe(...)`, slices the post-transcode 16 kHz mono PCM WAV into `ASR_STREAM_CHUNK_SECONDS`-long segments using Python's standard `wave` module, calls whisper-server `/inference` sequentially per chunk, and yields one SSE `data:` frame per chunk + one `event: complete` frame on completion + `event: error` on mid-stream failure. Non-streaming `POST /encounters/{id}/transcribe` (BE-014/016) MUST be preserved unchanged — it is the rollback path. The SSE envelope MUST mirror BE-013 (streaming draft) bit-for-bit so the frontend SSE parser can be lifted mechanically.
- **Inputs:**
  - SPEC.md#asr-layer-contract — streaming variant of the contract; rollback flag
  - backend/SPEC.md#asr-adapter — `LocalASRClient.stream_transcribe`, `TranscribeChunk` shape, env vars
  - backend/SPEC.md#transcribe-streaming-endpoint — endpoint contract, SSE frame envelope
  - backend/SPEC.md#transcribe-endpoint — non-streaming endpoint preserved unchanged
  - backend/SPEC.md#api-surface — error envelope, response_model rule
  - backend/SPEC.md#authentication — `get_current_clinician` dependency required
  - docs/adr/0003-streaming-asr-chunked.md — chunked-streaming approach, env-var rollback, latency profile
  - backend/app/infrastructure/asr/whisper_cpp_client.py (BE-014/016) — existing `_transcode_to_wav` reused; sequential `/inference` call shape established
  - backend/app/infrastructure/asr/client.py — `LocalASRClient` Protocol to extend
  - backend/app/infrastructure/asr/fake_client.py — `FakeLocalASRClient` to extend for tests
  - backend/app/interfaces/routers/drafts.py (BE-013) — SSE envelope precedent: `data: {...}\n\n`, `event: complete\ndata: {...}\n\n`, `event: error\ndata: {...}\n\n`
  - backend/app/usecases/draft.py (BE-013) — `stream_record_draft` async-generator pattern
  - backend/app/usecases/di.py — DI seam to extend with `make_stream_transcribe_audio`
  - backend/app/interfaces/routers/transcribe.py (BE-014/016) — extend; do NOT create a second router file
  - .claude/rules/local-llm-and-phi.md §1 §3 §4 — audio + transcript are PHI; SSE frames must respect masking
- **Acceptance:**
  - [ ] `app/infrastructure/asr/types.py` adds `TranscribeChunk` frozen dataclass: `text: str`, `chunk_index: int`, `chunk_count: int`, `done: bool`. Exported from `__init__.py`.
  - [ ] `app/infrastructure/asr/config.py` adds env-var parsing for `ASR_STREAM_CHUNK_SECONDS` (default 10, must be in [5, 20] inclusive — raises a configuration error at import time if outside), `ASR_STREAM_TOTAL_TIMEOUT_S` (default 180), `ASR_STREAM_FIRST_CHUNK_LATENCY_S` (default 25). Tests cover boundary cases (4 → error, 5 → ok, 20 → ok, 21 → error).
  - [ ] `app/infrastructure/asr/client.py` `LocalASRClient` Protocol gains `stream_transcribe(audio, params) -> AsyncIterator[TranscribeChunk]`. The Protocol is runtime-checkable; both `WhisperCppLocalASRClient` and `FakeLocalASRClient` MUST satisfy it.
  - [ ] `app/infrastructure/asr/whisper_cpp_client.py` adds `_slice_wav_to_chunks(wav_bytes: bytes, chunk_seconds: int) -> list[bytes]`: uses `wave.open(io.BytesIO(wav_bytes), "rb")` to read the PCM frames, slices into chunk-second segments aligned on sample boundaries, rebuilds a complete WAV per slice using `wave.open(io.BytesIO(), "wb")`. No temp files. The last slice may be shorter than `chunk_seconds`. Returns at least 1 slice (the original WAV) if audio shorter than `chunk_seconds`.
  - [ ] `_slice_wav_to_chunks` unit tests: 60 s audio → 6 slices @ 10 s; 25 s audio → 3 slices (10/10/5); 5 s audio → 1 slice; rejects non-WAV header (raises `ASRError`); rejects non-16kHz / non-mono / non-PCM_S16LE (raises `ASRError`).
  - [ ] `WhisperCppLocalASRClient.stream_transcribe(audio, params)` implementation: (1) call existing `_transcode_to_wav(audio.audio_bytes, audio.content_type)`; (2) call `_slice_wav_to_chunks(wav_bytes, ASR_STREAM_CHUNK_SECONDS)`; (3) iterate slices, POST each to `/inference` sequentially with the same multipart form-data shape as `transcribe`, yielding `TranscribeChunk(text=text, chunk_index=i, chunk_count=N, done=False)` per success; (4) after the last chunk, yield `TranscribeChunk(text=assembled, chunk_index=N-1, chunk_count=N, done=True)`. Each chunk's text is empty-text-gated identically to BE-016 — empty text → `ASRError("transcribe returned empty text (chunk N)")`. Per-chunk httpx timeout is `ASR_TIMEOUT_S=90`. Audio bytes / wav bytes / sliced bytes are released as soon as the loop advances past their slice (no buffer accumulation in the iterator scope).
  - [ ] `FakeLocalASRClient.stream_transcribe(audio, params)` implementation: yields N=3 chunks by default (split fixture transcript into thirds), with optional `per_chunk_delay_s: float = 0.0`, `force_error_at_chunk: int | None = None`, `force_timeout: bool = False`, `force_total_timeout: bool = False`. Errors raise `ASRError` from inside the iterator at the configured chunk.
  - [ ] `app/usecases/transcribe_stream.py` exports `stream_transcribe_audio(*, audio, params, encounter_id, clinician_id, asr, encounter_repo) -> AsyncGenerator[TranscribeChunk, None]`: (1) verify encounter exists (`EncounterNotFound` raised synchronously before any ASR work — router maps to 404); (2) `async for chunk in asr.stream_transcribe(audio, params)` with `asyncio.wait_for(..., timeout=ASR_STREAM_TOTAL_TIMEOUT_S)` wrapped at the per-chunk await boundary (raises `ASRError(..., timeout=True)` on total-timeout); (3) yield each chunk. No DB writes. No audit log. INFO log: `short_id(encounter_id)`, `short_id(clinician_id)`, `chunk_index`, `chunk_count`. DEBUG log: chunk text length only (never the text body).
  - [ ] `app/usecases/di.py` adds `make_stream_transcribe_audio(...)` factory + `StreamTranscribeAudioCallable = Callable[[AudioPayload, TranscribeParams | None, UUID, UUID], AsyncGenerator[TranscribeChunk, None]]`. Mirrors `make_stream_record_draft` (BE-013).
  - [ ] `app/interfaces/routers/transcribe.py` is extended (NOT duplicated) with a new endpoint `POST /encounters/{encounter_id}/transcribe/stream`. The endpoint: (a) validates content-type (415), payload size ≤2 MB (422), header (401) synchronously — same checks as `post_transcribe`; (b) pre-reads the first chunk from the usecase generator to surface `EncounterNotFound` synchronously as 404 (mirrors BE-013 router pattern); (c) wraps remaining chunks in a `StreamingResponse(_sse_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})`.
  - [ ] SSE frame format (binding — identical to BE-013 envelope):
    - Chunk: `data: {"text":"<chunk_text>","chunk_index":<int>,"chunk_count":<int>,"done":false}\n\n`
    - Completion: `event: complete\ndata: {"full_text":"<assembled>","duration_seconds":<float|null>,"chunk_count":<int>}\n\n`
    - Error: `event: error\ndata: {"code":"transcription_unavailable"|"transcription_timeout","chunk_index":<int>}\n\n`. After an error frame the stream closes.
  - [ ] Error mapping: `ASRError(timeout=True)` mid-stream → `transcription_timeout`; any other `ASRError` mid-stream → `transcription_unavailable`. `exc.masked_context` MUST NOT appear in any SSE frame.
  - [ ] PHI logging discipline at router level: `short_id(encounter_id)` and chunk_index at INFO; `mask_phi(chunk.text)` at DEBUG only. Filename from multipart is dropped at router boundary. No audio bytes, no PCM slice bytes, no raw transcript text in any logger call at INFO or above.
  - [ ] Cancellation: when the HTTP connection drops (client AbortController), the SSE generator's outer `try/finally` MUST release the in-flight subprocess (transcode) via `proc.kill()` and any pending httpx call (httpx auto-cancels on context exit). Use FastAPI's standard `StreamingResponse` close hook — no custom cancellation channel.
  - [ ] Layer rule: `grep -RnE '^from app\.infrastructure' backend/app/interfaces/routers/transcribe.py` → 0 hits (preserves the existing rule). `grep -RnE '^from app\.infrastructure\.asr' backend/app/{domain,usecases,interfaces}` returns hits only from `usecases/di.py`, `usecases/transcribe.py`, `usecases/transcribe_stream.py`.
  - [ ] Non-streaming endpoint preserved bit-for-bit: `post_transcribe`, its tests (`tests/interfaces/test_transcribe_router.py` existing 9 tests), and `transcribe_audio` usecase tests (`tests/usecases/test_transcribe.py` existing 5 tests) MUST continue to pass unchanged. New tests are additive.
  - [ ] Usecase tests in `tests/usecases/test_transcribe_stream.py`: (a) happy path — 3-chunk fake yields 3 data frames + 1 completion in order; (b) `EncounterNotFound` raised before any ASR call; (c) `ASRError` at chunk N → iterator stops at chunk N, no further yields; (d) total-timeout → `ASRError(timeout=True)` at the wait_for boundary; (e) clinician_id and encounter_id logged via `short_id(...)` only.
  - [ ] Router tests extended in `tests/interfaces/test_transcribe_router.py`: (f) 200 SSE happy path asserting raw frame bytes contain `data:`, `event: complete`; (g) 401 missing header; (h) 404 unknown encounter (synchronous, before stream opens); (i) 415 unsupported content-type; (j) 422 payload too large; (k) mid-stream `transcription_unavailable` error frame (force_error_at_chunk=1); (l) mid-stream `transcription_timeout` error frame (force_total_timeout=True); (m) frame payload contains no `masked_context` substring or raw audio length value.
  - [ ] Infrastructure tests in `tests/infrastructure/asr/test_whisper_cpp_client.py`: `_slice_wav_to_chunks` unit cases per acceptance bullet above; `stream_transcribe` happy path with mocked httpx; per-chunk empty-text gating raises `ASRError`. `tests/infrastructure/asr/test_fake_client.py` extended with stream cases (default chunk count, force_error_at_chunk, force_timeout, per_chunk_delay_s).
  - [ ] G0: docker-compose env vars updated — `backend` service gains `ASR_STREAM_CHUNK_SECONDS=10`, `ASR_STREAM_TOTAL_TIMEOUT_S=180`, `ASR_STREAM_FIRST_CHUNK_LATENCY_S=25` (defaults match SPEC). No new ports, no new services.
  - [ ] G1 pyright 0 errors; G2 ruff clean; G3 pytest passes net new tests ≥+15 over BE-016 baseline.
  - [ ] G4 security-check: no hosted-ASR SDKs added; chunked PCM slices never written to disk; SSE frame payload contains only `code` and `chunk_index` on errors (verified via test); `mask_phi`/`short_id` discipline preserved.
  - [ ] G5 cost-check: streaming first-chunk p95 ≤25 s and total p95 ≤180 s on the reference CPU for a 60 s synthetic clip via the `Fake` path with realistic `per_chunk_delay_s`; memory footprint unchanged from BE-016 (sequential calls reuse loaded whisper.cpp model).
- **Out-of-scope:**
  - Parallel chunk processing (whisper.cpp serializes; rejected in ADR-0003).
  - Real-time mic→whisper continuous streaming (different audio-capture paradigm; ADR-required).
  - Chunk overlap (0 s in v1; tracked as ADR-0003 follow-up).
  - Removing or modifying `POST /encounters/{id}/transcribe` (rollback path; must remain unchanged).
  - kotoba-whisper variant swap (ADR-0001 follow-up).
  - Audio or transcript persistence; audit-log row for transcription.
  - Multi-clip queueing; resumable streams.
  - Frontend changes (FE-013).
- **Open-questions:** _(none)_
- **Inference Impact:** yes; ASR streaming path; `whisper.cpp medium-q5_0`; `ASR_TIMEOUT_S=90` per chunk; `ASR_STREAM_TOTAL_TIMEOUT_S=180` end-to-end; first-chunk p95 ≤25 s; co-resident with `gemma4:e4b`; memory footprint ~10 GiB LLM + ~1 GiB ASR, unchanged from BE-016.
- **Data Sensitivity:** PHI; audio bytes, chunked PCM slices, chunk transcript text, and assembled transcript are PHI per ADR-0001 and `.claude/rules/local-llm-and-phi.md` §3. Never echoed in INFO logs; never in SSE error frame payloads; never persisted past the request lifetime.
- **Gates Touched:** G1, G2, G3, G4, G5, G6, G7
- **Affected Layers:** infrastructure (extend `LocalASRClient` Protocol, `WhisperCppLocalASRClient`, `FakeLocalASRClient`, `types.py`, `config.py`), usecases (new `transcribe_stream.py`, extend `di.py`), interfaces (extend `routers/transcribe.py`)
- **Status:** pending
