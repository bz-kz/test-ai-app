# Frontend TASKS

Active task list for the frontend. Each task is a Block per `docs/handoff-contract.md`. Generator owns this file (per `AGENTS.md` §3); Planner seeds initial tasks.

## How to add a task

1. Copy the Sample Task Block below; rename `## Sample: …` to `## <Feature title>`.
2. Fill every required field. `Open-questions` MUST be `_(none)_` before handoff.
3. Add a row to the Task Index. Use status values: `pending`, `in-progress`, `qa`, `done`, `blocked`.
4. On Evaluator pass, flip the row to `done`. Do not delete completed Blocks; they are the implementation log.

## Task Index

| ID     | Title                             | Status | Gates Touched      | Owner     |
| ------ | --------------------------------- | ------ | ------------------ | --------- |
| FE-001 | Frontend foundation + Button atom | done   | G1, G2, G3, G6, G7 | Generator |

---

## Frontend Foundation + Button Atom (FE-001)

- **Goal:** Establish Tailwind 4 + Vitest/jsdom testing infrastructure and deliver a fully-typed, accessible Button atom that implements all four variants and three sizes from DESIGN.md.
- **Inputs:**
  - frontend/SPEC.md#atomic-design-mapping — component placement rules
  - DESIGN.md#buttons — variant fills, sizes, disabled state
  - DESIGN.md#accessibility-bar — focus ring, opacity rules
  - docs/handoff-contract.md#2 — Block schema
- **Acceptance:**
  - [x] `frontend/src/test/setup.ts` exists and imports `@testing-library/jest-dom`; `vitest.config.ts` sets `globals: true` and references setup file.
  - [x] `frontend/src/components/atoms/Button.tsx` exports default `Button` via `React.forwardRef`; props: `variant`, `size`, `loading`, `disabled`, `type`, standard `onClick`/`children`/`aria-*`/`data-*`.
  - [x] All four variants (`primary`, `secondary`, `ghost`, `destructive`) match DESIGN.md fills, text colours, hover fills.
  - [x] All three sizes (`sm`, `md`, `lg`) match DESIGN.md padding/text/height spec.
  - [x] `loading={true}` renders an SVG spinner, sets `aria-busy="true"`, disables the underlying button.
  - [x] Disabled and loading states apply `disabled:opacity-40 disabled:cursor-not-allowed disabled:pointer-events-none`.
  - [x] Focus visible ring: `focus-visible:ring-2 focus-visible:ring-navy focus-visible:ring-offset-2`.
  - [x] `data-variant` attribute set for test hooks.
  - [x] `frontend/src/components/atoms/__tests__/Button.test.tsx` — 7 test cases all pass (`npm test -- --run`).
  - [x] G1 `npx tsc --noEmit` — 0 errors.
  - [x] G2 `npx eslint .` and `npx prettier --check .` — clean.
  - [x] G3 `npm test -- --run` — 9/9 tests pass (constants suite + Button suite).
- **Out-of-scope:** Other atoms (Input, Chip, Checkbox, RadioButton, Tooltip, Badge), molecules, organisms, services, hooks, page composition.
- **Open-questions:** _(none)_
- **Inference Impact:** no
- **Data Sensitivity:** none
- **Gates Touched:** G1, G2, G3, G6, G7
- **Affected Layers:** atoms

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
