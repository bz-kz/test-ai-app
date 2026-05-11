# Frontend TASKS

Active task list for the frontend. Each task is a Block per `docs/handoff-contract.md`. Generator owns this file (per `AGENTS.md` §3); Planner seeds initial tasks.

## How to add a task

1. Copy the Sample Task Block below; rename `## Sample: …` to `## <Feature title>`.
2. Fill every required field. `Open-questions` MUST be `_(none)_` before handoff.
3. Add a row to the Task Index. Use status values: `pending`, `in-progress`, `qa`, `done`, `blocked`.
4. On Evaluator pass, flip the row to `done`. Do not delete completed Blocks; they are the implementation log.

## Task Index

| ID      | Title                                                    | Status | Gates Touched              | Owner     |
| ------- | -------------------------------------------------------- | ------ | -------------------------- | --------- |
| FE-001  | Frontend foundation + Button atom                        | done   | G1, G2, G3, G6, G7         | Generator |
| FE-002  | Patient Search by MRN                                    | done   | G1, G2, G3, G4, G6, G7     | Generator |
| FE-003  | Record Draft generation UI                               | done   | G1, G2, G3, G4, G5, G6, G7 | Generator |
| FE-004  | Draft edit and finalize UI                               | done   | G1, G2, G3, G4, G6, G7     | Generator |
| FE-005  | Final correction UI + FE-004 fixes                       | done   | G1, G2, G3, G4, G6, G7     | Generator |
| FE-006  | Auto-load draft + correction chain UI                    | done   | G1, G2, G3, G4, G6, G7     | Generator |
| FE-007  | Navigation pages (Patient detail + Encounter detail)     | done   | G1, G2, G3, G4, G6, G7     | Generator |
| FE-007b | Navigation pages — detail pages + helper (FE-007 part 2) | done   | G0, G1, G2, G3, G4, G6, G7 | Generator |

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

## Draft edit and finalize UI (FE-004)

- **Goal:** Extend `/encounters/[encounterId]/draft` with the full AI Output Patterns action set: Edit (inline edit of the AI draft content + PATCH), Approve (finalize → record_final + POST), and ConfidencePill visualisation when confidence ≤ 0.5. After Approve, the page transitions to a "finalized" state that renders record_final's content with an immutability cue. Regenerate remains mapped to the existing "下書きを生成" button.
- **Inputs:**
  - frontend/SPEC.md#ai-output-patterns — ConfidencePill; fixed Regenerate/Edit/Approve button order
  - frontend/SPEC.md#layer-rules — services own fetch; hooks own state; no any
  - DESIGN.md#ai-output-patterns — Button variants; ConfidencePill warning/neutral
  - SPEC.md#domain-glossary — record_draft, record_final, predecessor_id
  - .claude/rules/local-llm-and-phi.md §3 §4 — draft.content and final.content are PHI
  - backend/app/interfaces/routers/drafts.py — PATCH /drafts/{draft_id} (BE-007), POST /drafts/{draft_id}/finalize
  - backend/app/interfaces/routers/finals.py — GET /finals/{final_id}
  - Existing: Button, Input, TextArea, FormField, AIIndicatedText atoms/molecules; apiFetch; maskPhi; RecordDraft type; useGenerateDraft hook
- **Acceptance:**
  - [x] `src/components/molecules/ConfidencePill.tsx` — renders warning/neutral pill; null confidence → null; aria-label "AI 信頼度 {value}"; rounds to 2dp; 10 unit tests green.
  - [x] `src/types/recordFinal.ts` — RecordFinal type matching backend FinalRead shape.
  - [x] `src/services/drafts.ts` extended — editRecordDraft, finalizeRecordDraft, getRecordFinalById; EditDraftResult, FinalizeDraftResult, GetFinalResult discriminated unions; no PHI in logs; unit tests cover happy + error paths.
  - [x] `src/hooks/useDraftLifecycle.ts` — mode (view/editing/finalized), enterEditMode, cancelEdit, saveEdit, approve, final, status, error; AbortController; JP error messages; 18 unit tests green.
  - [x] Draft page extended: success+view renders 3 action buttons in fixed order (再生成/編集/承認) + ConfidencePill; editing mode renders TextArea + キャンセル/更新; finalized mode renders 確定済みバッジ + 確定カルテ content, no action buttons.
  - [x] Page integration tests extended (29 total); FE-003 latency tiers preserved.
  - [x] Cross-cutting: 0 fetch( in components/app; 0 storage writes; 0 console.\*; 0 : any.
  - [x] G1 npx tsc --noEmit — 0 errors.
  - [x] G2 npx eslint . && npx prettier --check . — clean.
  - [x] G3 npm test -- --run — 150/150 tests pass.
  - [x] G4 security-check — no hosted-LLM SDKs; no direct LLM calls outside infrastructure; no PHI in logs/storage.
- **Out-of-scope:** Final correction flow (POST /finals/{id}/correct — FE-005). Encounter list / patient detail page. ConfidencePill in non-AIIndicatedText contexts. Streaming UI. RecordDraftEditor organism formalisation. Authentication around clinician_id.
- **Open-questions:** _(none)_
- **Inference Impact:** no — FE-004 issues no inference calls; PATCH and POST /finalize are DB-write endpoints.
- **Data Sensitivity:** PHI; draft.content and final.content are free-text clinical narrative; never in console.\*, never in browser storage, never in URL; operational reads (page render) are explicitly requested by the caller per .claude/rules/local-llm-and-phi.md §4.
- **Gates Touched:** G1, G2, G3, G4, G6, G7
- **Affected Layers:** molecules (ConfidencePill), hooks (useDraftLifecycle), services (drafts extended), types (recordFinal), app (page extended)

---

## Final correction UI + FE-004 follow-ups (FE-005)

- **Goal:** Make the finalized record correctable from the UI by consuming BE-008's correction-chain endpoints, and fix two ergonomics gaps the Evaluator flagged on FE-004: (a) `AIIndicatedText` aria-label hardcode, (b) `saveEdit` not propagating the updated draft back to visible state.
- **Inputs:**
  - frontend/SPEC.md#ai-output-patterns — Regenerate / Edit / Approve action set; Correction is the natural successor for record_final corrections per the clinical lifecycle
  - SPEC.md#domain-glossary — `record_final`, `predecessor_id` for correction lineage
  - backend/app/interfaces/routers/finals.py — POST `/finals/{final_id}/correct` body `{content, clinician_id}`, response 201 `FinalRead`; GET `/finals/{final_id}/chain` returns `list[FinalRead]`; 404 `final_not_found`; 422 validation
  - Existing: Button, TextArea, AIIndicatedText, ConfidencePill, useDraftLifecycle, useGenerateDraft, apiFetch, maskPhi, RecordDraft, RecordFinal types
- **Acceptance:**
  - [x] `AIIndicatedText` gains `ariaLabel?: string` prop; when provided, overrides default `aria-label="AI 生成テキスト"`; backwards-compatible.
  - [x] Existing 7 AIIndicatedText tests green; ≥2 new tests cover `ariaLabel` prop override.
  - [x] `useGenerateDraft` exposes `setDraft: (next: RecordDraft | null) => void`; existing tests still green.
  - [x] `useDraftLifecycle` accepts `onDraftUpdated?: (next: RecordDraft) => void` callback; `saveEdit` success calls it with the updated draft; ≥1 new test confirms this.
  - [x] Page wires `useDraftLifecycle({ ..., onDraftUpdated: gen.setDraft })`; after `saveEdit` success, AIIndicatedText re-renders with new content without refresh.
  - [x] `services/finals.ts` added with `correctRecordFinal` and `getFinalChain`; 6-8 unit tests mocking `apiFetch`.
  - [x] `hooks/useCorrectFinal.ts` added; returns `{ mode, content, setContent, enter, cancel, submit, status, error, correctedFinal }`; AbortController for in-flight cancel; tests cover state transitions and error paths.
  - [x] Page finalized state: renders `AIIndicatedText` with `ariaLabel="確定カルテ"`, optional `ConfidencePill`, and a 訂正 Button.
  - [x] Clicking 訂正 shows TextArea pre-filled with current final content + キャンセル / 更新 buttons.
  - [x] Submit success swaps `currentFinal` to the new `RecordFinal` and returns to finalized view.
  - [x] Submit error renders JP error string in `role="alert"`.
  - [x] Page integration tests extended: finalized shows 訂正 button; correcting mode pre-fills TextArea; submit calls service and updates display; error paths render correctly; AIIndicatedText announced as "確定カルテ".
  - [x] Cross-cutting greps clean: no `fetch` outside services; no `console.*`; no PHI in storage/URL; no `any`; no `dangerouslySetInnerHTML`.
  - [x] G1 `npx tsc --noEmit` — 0 errors.
  - [x] G2 `npx eslint . && npx prettier --check .` — clean.
  - [x] G3 `npm test -- --run` — all tests pass.
  - [x] G4 security-check — no PHI in logs or storage; no hosted-LLM SDKs.
- **Out-of-scope:** Auto-load existing draft on page mount (FE-004 NOTE 3). Correction chain visualisation (FE-006). Encounter list / patient detail pages. Authentication / role-gated PHI reads. INF-003 LLM memory budget alignment. Streaming UI.
- **Open-questions:** _(none)_
- **Inference Impact:** no
- **Data Sensitivity:** PHI; `final.content` and correction `content` are free-text clinical narrative per `.claude/rules/local-llm-and-phi.md` §3; masked before any logger call; never in browser storage or URL.
- **Gates Touched:** G1, G2, G3, G4, G6, G7
- **Affected Layers:** molecules (AIIndicatedText prop fix), hooks (useDraftLifecycle propagation + new useCorrectFinal), services (new finals service), app (page extension)

---

## Auto-load draft + correction chain UI (FE-006)

- **Goal:** Two page enhancements on `/encounters/[encounterId]/draft`: (1) auto-load the latest existing draft on page mount and seed it into `useGenerateDraft` so the user does not need to regenerate; (2) render the predecessor correction chain in `finalized` mode below the AIIndicatedText using the `ChainList` molecule.
- **Inputs:**
  - backend/app/interfaces/routers/encounters.py — `GET /encounters/{id}/drafts` returns `list[DraftRead]` ordered by `created_at` DESC (BE-009 contract)
  - backend/app/interfaces/routers/finals.py — `GET /finals/{id}/chain` returns `list[FinalRead]` oldest→newest (BE-008 contract); 404 `final_not_found`
  - frontend/src/services/drafts.ts — existing `apiFetch` HTTP client; extended with `listDraftsByEncounter`
  - frontend/src/services/finals.ts — existing `getFinalChain`; reused for chain UI
  - frontend/src/hooks/useGenerateDraft.ts — `setDraft` used to seed auto-loaded draft
  - frontend/src/hooks/useDraftLifecycle.ts — `mode` drives conditional chain fetch
  - frontend/src/components/molecules/AIIndicatedText.tsx — renders finalized content
  - frontend/src/types/{recordDraft,recordFinal}.ts — existing types
  - .claude/rules/local-llm-and-phi.md §3, §4 — PHI in content; no console/storage/URL
- **Acceptance:**
  - [x] `listDraftsByEncounter(encounterId, opts?)` added to `services/drafts.ts`; returns `ListDraftsResult`; unit tests cover 200+drafts, 200+empty, error (6 tests total in drafts.test.ts).
  - [x] `hooks/useEncounterDrafts.ts` — `status/drafts/latest/error/load`; AbortController per call; ≥6 unit tests green.
  - [x] `hooks/useFinalChain.ts` — `status/chain/error/load`; `not_found` tag; AbortController; ≥5 unit tests green.
  - [x] `components/molecules/ChainList.tsx` — `<ol>` with `<li>` per entry; oldest→newest order; current head `font-bold`; excerpt ≤80 chars + ellipsis; `aria-label` includes 第N版 + date; empty chain renders null; ≥5 unit tests green.
  - [x] Page extended: `useEncounterDrafts.load(encounterId)` called on mount; auto-seeds draft when `status=loaded && latest !== null && draft === null`; shows "下書きを確認しています…" while loading; finalized mode calls `useFinalChain.load(currentFinal.id)`; renders `ChainList` on loaded; loading/error/not_found fallback messages.
  - [x] Page integration tests: auto-load loading indicator; auto-load empty; auto-seed setDraft called; draft present → no setDraft; chain renders in finalized; chain not_found/error renders fallback.
  - [x] Cross-cutting: 0 `fetch(` in components/app; 0 storage writes; 0 `console.*`; 0 `: any`; no raw HTML injection.
  - [x] G1 `npx tsc --noEmit` — 0 errors.
  - [x] G2 `npx eslint . && npx prettier --check .` — clean.
  - [x] G3 `npm test -- --run` — 221/221 tests pass.
  - [x] G4 security-check — no hosted-LLM SDKs; no PHI in logs/storage; no direct LLM calls outside infrastructure.
- **Out-of-scope:** Chain editing or merging UI; bulk operations across multiple drafts; non-latest draft selection; auth-gated draft visibility; encounter/patient navigation pages; streaming UI.
- **Open-questions:** _(none)_
- **Inference Impact:** no
- **Data Sensitivity:** PHI; existing draft `content` and final chain `content` excerpts are rendered in the operational-read path per `.claude/rules/local-llm-and-phi.md` §4; no PHI in console/storage/URL.
- **Gates Touched:** G1, G2, G3, G4, G6, G7
- **Affected Layers:** molecules (ChainList), hooks (useEncounterDrafts + useFinalChain), services (listDraftsByEncounter), app (page extension)

---

## Navigation pages — detail pages + helper (FE-007b)

- **Goal:** Deliver patient detail page, encounter detail page, `useCreateEncounter` hook, `listFinalsByEncounter` in `finals.ts`, and the search-result link — completing the full navigation layer started in FE-007a.
- **Inputs:**
  - frontend/SPEC.md#layer-rules — pages use hooks; hooks use services; services own fetch
  - frontend/SPEC.md#atomic-design-mapping — component placement
  - DESIGN.md#colors, #cards, #lists — visual spec
  - .claude/rules/local-llm-and-phi.md §3, §4 — PHI in patient/encounter/draft/final fields; no console/storage/URL
  - frontend/src/hooks/usePatientDetail.ts — wired in FE-007a
  - frontend/src/hooks/useEncounterDetail.ts — wired in FE-007a
  - frontend/src/services/encounters.ts — createEncounter, listFinalsByEncounter
- **Acceptance:**
  - [x] `services/finals.ts` extended: `listFinalsByEncounter(encounterId, opts?)` added; 3 new unit tests in `finals.test.ts` (found, 404→empty, server_error).
  - [x] `hooks/useCreateEncounter.ts`: idle → submitting → success → idle state machine; `reset()` clears `lastCreated`; AbortController; JP error strings; 8 unit tests.
  - [x] `app/patients/[patientId]/page.tsx`: "use client"; 4 loading states (loading/idle → "読み込み中…", not_found, error, loaded); patient card with all fields; encounter list newest-first with `<Link href="/encounters/{id}">` per row; new-encounter inline form; success confirmation "✓ 受診を追加しました" for 2s; 11 page tests.
  - [x] `app/encounters/[encounterId]/page.tsx`: "use client"; 4 loading states; encounter card (encountered_at, clinician_id as 8-hex-char short form, created_at); drafts list (first 80 chars + …); finals list (same shape); "下書きを作成 / 編集" Link to `/encounters/{id}/draft`; 9 page tests.
  - [x] `app/patients/page.tsx` (FE-002): patient card wrapped in `<Link href="/patients/{id}">`.
  - [x] G0 `docker compose build frontend && docker compose up -d frontend` — all services running.
  - [x] G1 `npx tsc --noEmit` — 0 errors.
  - [x] G2 `npx eslint . && npx prettier --check .` — clean.
  - [x] G3 `npm test -- --run` — 285/285 tests pass.
  - [x] G4 security-check — no hosted-LLM SDKs; no PHI in console/storage/URL; no dangerouslySetInnerHTML; no direct fetch in pages.
- **Out-of-scope:** Patient creation/edit UI; encounter-to-patient back-link (patient_id not shown in URL); auth-gated PHI reads; pagination; SSR pre-fetch; MaskToggle on detail pages.
- **Open-questions:** _(none)_
- **Inference Impact:** no
- **Data Sensitivity:** PHI; family_name, given_name, MRN, DOB, draft/final content excerpts are displayed in operational-read path per `.claude/rules/local-llm-and-phi.md` §4; no PHI in console, storage, or URL.
- **Gates Touched:** G0, G1, G2, G3, G4, G6, G7
- **Affected Layers:** hooks (useCreateEncounter), services (finals extension), app (two new pages + patients search update)

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
