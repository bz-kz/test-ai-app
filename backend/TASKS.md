# Backend TASKS

Active task list for the backend. Each task is a Block per `docs/handoff-contract.md`. Generator owns this file (per `AGENTS.md` §3); Planner seeds initial tasks.

## How to add a task

1. Copy the Sample Task Block below; rename `## Sample: …` to `## <Feature title>`.
2. Fill every required field. `Open-questions` MUST be `_(none)_` before handoff.
3. Add a row to the Task Index. Use status values: `pending`, `in-progress`, `qa`, `done`, `blocked`.
4. On Evaluator pass, flip the row to `done`. Do not delete completed Blocks; they are the implementation log.

## Task Index

| ID                                            | Title | Status | Gates Touched | Owner |
| --------------------------------------------- | ----- | ------ | ------------- | ----- |
| _(empty — first feature task will be BE-001)_ |       |        |               |       |

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
