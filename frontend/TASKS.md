# Frontend TASKS

Active task list for the frontend. Each task is a Block per `docs/handoff-contract.md`. Generator owns this file (per `AGENTS.md` §3); Planner seeds initial tasks.

## How to add a task

1. Copy the Sample Task Block below; rename `## Sample: …` to `## <Feature title>`.
2. Fill every required field. `Open-questions` MUST be `_(none)_` before handoff.
3. Add a row to the Task Index. Use status values: `pending`, `in-progress`, `qa`, `done`, `blocked`.
4. On Evaluator pass, flip the row to `done`. Do not delete completed Blocks; they are the implementation log.

## Task Index

| ID     | Title                             | Status | Gates Touched              | Owner     |
| ------ | --------------------------------- | ------ | -------------------------- | --------- |
| FE-001 | Frontend foundation + Button atom | done   | G1, G2, G3, G6, G7         | Generator |
| FE-002 | Patient Search by MRN             | done   | G1, G2, G3, G4, G6, G7     | Generator |
| FE-003 | Record Draft generation UI        | done   | G1, G2, G3, G4, G5, G6, G7 | Generator |

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

## Patient Search by MRN (FE-002)

- **Goal:** Render a `/patients` page with an MRN search field that calls `GET /patients?mrn=<value>` (BE-004) and displays the resulting patient or an empty/not-found/error state. Establishes the project's HTTP client, service layer, hook pattern, the `Input` atom, the `FormField` molecule, and the `MrnSearchField` molecule.
- **Inputs:**
  - frontend/SPEC.md#frontend-mission — clinician-first UI, PHI in browser storage prohibited
  - frontend/SPEC.md#atomic-design-mapping — atom/molecule/organism placement rules
  - frontend/SPEC.md#layer-rules — pages use hooks; hooks use services; services own fetch
  - frontend/SPEC.md#latency-ux-budget — spinner tier for sub-300ms endpoint
  - DESIGN.md#inputs — Input visual spec
  - SPEC.md#domain-glossary — canonical identifiers: patient, mrn, family_name, given_name, date_of_birth
  - backend/app/interfaces/routers/patients.py — PatientRead response shape; 404 detail shape
  - .claude/rules/local-llm-and-phi.md §3, §4 — PHI masking and storage rules
- **Acceptance:**
  - [x] `src/lib/api.ts` exports `apiFetch<T>` with `ApiResult<T>` discriminated union; never throws on non-2xx.
  - [x] `src/lib/maskPhi.ts` exports `maskPhi(value: unknown): string`; unit tested.
  - [x] `src/services/patients.ts` exports `searchPatientsByMrn` using `apiFetch`; maps to `SearchPatientResult`.
  - [x] `src/hooks/useMrnSearch.ts` exports `useMrnSearch()` with debounce 200ms, AbortController, and idle/searching/found/not_found/error states; unit tested.
  - [x] `src/components/atoms/Input.tsx` exports `Input` via `forwardRef`; `error` prop, focus ring, disabled state; unit tested.
  - [x] `src/components/molecules/FormField.tsx` exports `FormField`; label/htmlFor association, helper/error line; unit tested.
  - [x] `src/components/molecules/MrnSearchField.tsx` exports `MrnSearchField`; presentation-only; JP strings; unit tested.
  - [x] `src/app/patients/page.tsx` composes `MrnSearchField` + `useMrnSearch`; four UX states; no fetch, no storage writes, no console logs.
  - [x] Optional: `src/app/patients/__tests__/page.test.tsx` covering all four UX states.
  - [x] Cross-cutting: 0 `fetch(` in components/app; 0 storage writes; 0 console.\*; 0 `: any`.
  - [x] G1 `npx tsc --noEmit` — 0 errors.
  - [x] G2 `npx eslint . && npx prettier --check .` — clean.
  - [x] G3 `npm test -- --run` — all tests pass.
  - [x] G4 security-check — no PHI in logs or storage; no hosted-LLM SDKs.
- **Out-of-scope:** PatientCard organism; patient creation/edit UI; encounter list; MaskToggle; ConfidencePill; search history/URL sync; toast notifications; i18n; SSR pre-fetch.
- **Open-questions:** _(none)_
- **Inference Impact:** no
- **Data Sensitivity:** PHI; MRN, family_name, given_name, date_of_birth are PHI. Never echoed in console.\*, never persisted in browser storage. Use maskPhi for any debug log.
- **Gates Touched:** G1, G2, G3, G4, G6, G7
- **Affected Layers:** atoms, molecules, hooks, services, app (page), lib (api.ts + maskPhi.ts)

---

## Record Draft generation UI (FE-003)

- **Goal:** Render `/encounters/[encounterId]/draft` where a clinician types a clinical narrative into a textarea, clicks "下書きを生成", waits while the local Gemma 4 E4B produces a SOAP-shaped draft, and sees the AI output rendered with `<AIIndicatedText>`. Establishes the `TextArea` atom, the `AIIndicatedText` molecule, the five latency-UX tiers, the `useGenerateDraft` hook, and the `createRecordDraft` service.
- **Inputs:**
  - frontend/SPEC.md#atomic-design-mapping — TextArea (new atom), AIIndicatedText (new molecule)
  - frontend/SPEC.md#ai-output-patterns — left border + AI icon; body text must be escaped (no raw HTML injection)
  - frontend/SPEC.md#latency-ux-budget — five tiers: invisible / spinner / skeleton / skeleton+hint / cancel
  - frontend/SPEC.md#layer-rules — services own fetch; hooks own state; components no fetch; no any
  - DESIGN.md#ai-output-patterns — 3px left border in Tertiary Sage (#059669), AI icon
  - SPEC.md#inference-layer-contract — backend timeout 60s; output ≤1.5k tokens; PHI in prompt allowed
  - .claude/rules/local-llm-and-phi.md §3 §4 — clinical_input + draft.content are PHI; never in console/storage/URL
  - backend/app/interfaces/routers/drafts.py — DraftRead shape; 404 encounter_not_found; 503 inference_unavailable
- **Acceptance:**
  - [x] `src/components/atoms/TextArea.tsx` — forwardRef, TextAreaProps, error prop, rows=6 default, aria-invalid, disabled opacity, focus ring.
  - [x] `src/components/atoms/__tests__/TextArea.test.tsx` — renders textarea; disabled/error classes+attrs; onChange/value; ref; aria-invalid.
  - [x] `src/components/molecules/AIIndicatedText.tsx` — 4px left sage border, AI icon, label "AI 生成", role="article", aria-label, body text rendered via React children (no raw HTML injection).
  - [x] `src/components/molecules/__tests__/AIIndicatedText.test.tsx` — renders indicator+label+body; accessible name; body text is safe (children not injected as raw HTML).
  - [x] `src/types/recordDraft.ts` — RecordDraft type matching backend DraftRead shape.
  - [x] `src/services/drafts.ts` — createRecordDraft(encounterId, clinicalInput, opts) → CreateDraftResult; no PHI in logs.
  - [x] `src/hooks/useGenerateDraft.ts` — clinicalInput/setClinicalInput/status/draft/error/generate/cancel/elapsedMs; AbortController; ~100ms timer.
  - [x] `src/hooks/__tests__/useGenerateDraft.test.ts` — happy path; encounter_not_found; inference_unavailable; validation_error; cancel; elapsedMs; service mocked.
  - [x] `src/app/encounters/[encounterId]/draft/page.tsx` — "use client"; params via React.use(); FormField+TextArea; Button; five latency tiers; AIIndicatedText on success; no console/storage/fetch.
  - [x] `src/app/encounters/[encounterId]/draft/__tests__/page.test.tsx` — all five latency tiers + success + error states.
  - [x] Cross-cutting: 0 fetch( in components/app; 0 storage writes; 0 console.\*; 0 : any.
  - [x] G1 npx tsc --noEmit — 0 errors.
  - [x] G2 npx eslint . && npx prettier --check . — clean.
  - [x] G3 npm test -- --run — all tests pass.
  - [x] G4 security-check — no PHI in logs or storage; no hosted-LLM SDKs.
- **Out-of-scope:** Draft edit (PATCH), finalize (POST /finalize), ConfidencePill, streaming UI, RecordDraftEditor organism, encounter list UI, patient detail page, linking from patient search.
- **Open-questions:** _(none)_
- **Inference Impact:** yes; consumes BE-006's POST /encounters/{id}/drafts; UI accommodates Gemma's five latency tiers (≤300ms invisible, 300ms–1s spinner, 1–3s skeleton, 3–10s skeleton+hint, >10s cancel).
- **Data Sensitivity:** PHI; clinical_input (clinician's typed narrative) and draft.content (model output) are PHI per .claude/rules/local-llm-and-phi.md §3. Never echoed in console.\*, never written to browser storage, never appended to URL/searchParams.
- **Gates Touched:** G1, G2, G3, G4, G5, G6, G7
- **Affected Layers:** atoms (TextArea), molecules (AIIndicatedText), hooks (useGenerateDraft), services (drafts), app (page)

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
