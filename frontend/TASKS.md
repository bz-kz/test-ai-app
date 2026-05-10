# Frontend TASKS

Active task list for the frontend. Each task is a Block per `docs/handoff-contract.md`. Generator owns this file (per `AGENTS.md` §3); Planner seeds initial tasks.

## How to add a task

1. Copy the Sample Task Block below; rename `## Sample: …` to `## <Feature title>`.
2. Fill every required field. `Open-questions` MUST be `_(none)_` before handoff.
3. Add a row to the Task Index. Use status values: `pending`, `in-progress`, `qa`, `done`, `blocked`.
4. On Evaluator pass, flip the row to `done`. Do not delete completed Blocks; they are the implementation log.

## Task Index

| ID                                            | Title | Status | Gates Touched | Owner |
| --------------------------------------------- | ----- | ------ | ------------- | ----- |
| _(empty — first feature task will be FE-001)_ |       |        |               |       |

---

## Sample: Patient Search Field (FE-000)

- **Goal:** Render a search input on the records list page that filters by MRN within the local data set.
- **Inputs:**
  - SPEC.md#domain-glossary
  - frontend/SPEC.md#atomic-design-mapping
  - DESIGN.md#inputs
- **Acceptance:**
  - [ ] `<MrnSearchField>` molecule composed of `FormField` + atom `Input`.
  - [ ] Hook `useMrnSearch` debounces input at 200 ms and exposes `{query, results, status}`.
  - [ ] Service `searchPatientsByMrn` calls `GET /patients?mrn=` and normalises 404 to `[]`.
  - [ ] No raw MRN echoed to console on miss.
- **Out-of-scope:** Fuzzy match, server-side pagination, audit logging.
- **Open-questions:** _(none)_
- **Inference Impact:** no
- **Data Sensitivity:** PHI; mask MRN in any error log.
- **Gates Touched:** G1, G2, G3, G4, G6, G7
- **Affected Layers:** atoms, molecules, organisms
- **Status:** sample only — do not implement.
