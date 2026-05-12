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
| FE-008  | Streaming draft UI consumer                              | done   | G1, G2, G3, G4, G5, G6, G7 | Generator |
| FE-009  | RecordButton + VoiceCapture + draft-page wiring          | done   | G1, G2, G3, G4, G5, G6, G7 | Generator |
| FE-010  | Draft page auto-sync to finalized state                  | qa     | G1, G2, G3, G4, G6, G7     | Generator |

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

## Streaming draft UI consumer (FE-008)

- **Goal:** Replace the non-stream Generate action on `/encounters/[encounterId]/draft` with a streaming Generate that consumes BE-013's SSE endpoint. Show text accumulating in real-time inside an `<AIIndicatedText>` block with a blinking 1-px caret cursor per DESIGN.md Streaming Text spec; remove the cursor on stream completion. Wire the cancel button at the >10s latency tier.
- **Inputs:**
  - frontend/SPEC.md#ai-output-patterns — streaming caret cursor (1 px, body size, 70% opacity); cursor removed on completion
  - frontend/SPEC.md#latency-ux-budget — 5 tiers: ≤300ms invisible, 300-1000ms spinner, 1-3s skeleton, 3-10s skeleton+hint, >10s cancel
  - SPEC.md#inference-layer-contract — BE-013 SSE endpoint POST /encounters/{id}/drafts/stream
  - .claude/rules/local-llm-and-phi.md §3 §4 — clinical_input + streaming text + assembled content are PHI
  - DESIGN.md#ai-output-patterns — streaming caret spec
- **Acceptance:**
  - [x] `streamRecordDraft` added to `services/drafts.ts`; uses raw fetch with X-Clinician-Id header; parses SSE frames; calls onChunk/onComplete/onError callbacks; honours AbortSignal; no PHI in logs.
  - [x] Unit tests for `streamRecordDraft` in `services/__tests__/drafts.test.ts`: SSE happy path, 404/422/503/generic error, abort.
  - [x] `useGenerateDraft` extended with `generateStream()`, `streamingText: string`, `isStreaming: boolean`; existing non-stream `generate()` and tests preserved.
  - [x] Hook tests in `hooks/__tests__/useGenerateDraft.test.ts`: ≥4 new tests for stream chunks, completion, cancel, and error.
  - [x] `Cursor` atom in `frontend/src/components/atoms/Cursor.tsx`: 1px×1em box, body colour at 70% opacity, CSS blink animation, `aria-hidden="true"`.
  - [x] Draft page: `generateStream()` wired to "下書きを生成" button; during `isStreaming` renders `<AIIndicatedText>{streamingText}<Cursor /></AIIndicatedText>`; cursor removed on success; existing latency UX tiers preserved; cancel at >10s works.
  - [x] Cross-cutting: 0 `fetch(` in components/app; 0 `console.*`; 0 storage writes; 0 `: any`; no `dangerouslySetInnerHTML`.
  - [x] G1 `npx tsc --noEmit` — 0 errors.
  - [x] G2 `npx eslint . && npx prettier --check .` — clean.
  - [x] G3 `npm test -- --run` — ≥290 tests pass.
  - [x] G4 security-check — no PHI in logs; no hosted-LLM SDKs.
- **Out-of-scope:** Server-sent reconnect logic; resumable streams; per-encounter cancel that survives navigation; user-visible token counter; multi-stream concurrency.
- **Open-questions:** _(none)_
- **Inference Impact:** yes — UI now consumes the streaming inference path.
- **Data Sensitivity:** PHI; clinical_input + streaming text + assembled content are PHI per .claude/rules/local-llm-and-phi.md §3.
- **Gates Touched:** G1, G2, G3, G4, G5, G6, G7
- **Affected Layers:** services (extend drafts.ts), hooks (extend useGenerateDraft), atoms (Cursor), app (page swap to stream)

---

## RecordButton + VoiceCapture + draft-page wiring (FE-009)

- **Goal:** Add microphone-based voice input to the draft page: RecordButton atom, VoiceCapture molecule, useVoiceCapture hook, transcribe service, constants — all wired so the transcript appends to `clinical_input` without replacing existing text. Audio stays in memory only; never hits storage.
- **Status:** qa (G1/G2/G3/G4/G5 green; SPEC L113/L114 tier text fixed)
- **Inputs:**
  - frontend/SPEC.md#voice-capture — full acceptance criteria
  - frontend/SPEC.md#voice-input-latency-ux — latency UX tiers for ASR
  - frontend/SPEC.md#atomic-design-mapping — RecordButton (atom), VoiceCapture (molecule)
  - SPEC.md#asr-layer-contract — backend wire contract (POST /encounters/{id}/transcribe)
  - docs/adr/0001-voice-input-and-local-asr.md — Accepted; audio = PHI; no Web Speech API; no hosted ASR
  - .claude/rules/local-llm-and-phi.md §1, §3, §4 — audio blob + transcript are PHI; never in console/storage
- **Acceptance:**
  - [ ] `src/components/atoms/RecordButton.tsx` — idle/recording/uploading states; 48×48 px; aria-pressed; aria-label `"録音を開始"` (idle) / `"録音を停止"` (recording); keyboard accessible; disabled state; `motion-safe:animate-pulse` for recording.
  - [ ] `src/components/atoms/__tests__/RecordButton.test.tsx` — all visual states, onClick, disabled.
  - [ ] `src/services/transcribe.ts` — `transcribeAudio(encounterId, blob, opts)` → tagged union; X-Clinician-Id; no PHI in logs.
  - [ ] `src/services/__tests__/transcribe.test.ts` — each tagged-union branch with mocked fetch.
  - [ ] `src/hooks/useVoiceCapture.ts` — status machine `idle|requesting_permission|recording|uploading|success|error|permission_denied`; `getUserMedia({ audio: { channelCount: 1 } })`; start/stop/cancel; 60s auto-stop with `autoStopped` flag; AbortController; audio Blob in useRef only.
  - [ ] `src/hooks/__tests__/useVoiceCapture.test.ts` — state transitions, permission denial → permission_denied status, 60s auto-stop, cancel, success, error paths.
  - [ ] `src/components/molecules/VoiceCapture.tsx` — composes RecordButton + elapsed counter + error region; latency UX tiers; JP error strings from constants; aria-live; 60s auto-stop toast `"録音は60秒で停止しました"`; `permission_denied` alert.
  - [ ] `src/components/molecules/__tests__/VoiceCapture.test.tsx` — idle render, click→recording, mocked success→onTranscript, permission_denied, 503 path, 60s auto-stop toast, user-stop vs auto-stop differentiation.
  - [ ] `src/lib/constants.ts` — VOICE_CAPTURE_ERRORS (incl. `autoStopped`) + AUDIO_MAX_DURATION_S + AUDIO_MIME_TYPE + AUDIO_MAX_BYTES added.
  - [ ] `src/app/encounters/[encounterId]/draft/page.tsx` — VoiceCapture wired; onTranscript appends with newline separator; disabled while finalized/editing/streaming.
  - [ ] No FE-008 regression — all existing tests still pass.
  - [ ] G1 `npx tsc --noEmit` — 0 errors.
  - [ ] G2 `npx eslint . && npx prettier --check .` — clean.
  - [ ] G3 `npm test -- --run` — all tests pass; net count > 301.
  - [ ] G4 security-check — no hosted-ASR SDK; no Web Speech API; no MediaRecorder outside designated files; no storage writes; no PHI in console.
  - [ ] G5 cost-check — 60s cap enforced; latency UX tiers present; no heavy dep added.
- **Out-of-scope:** Backend changes; audio persistence; streaming partial transcripts; voice-to-direct-SOAP; recording >60s; waveform/VU meter.
- **Open-questions:** _(none)_
- **Inference Impact:** yes; consumes POST /encounters/{id}/transcribe ASR path.
- **Data Sensitivity:** PHI; audio bytes + transcript are PHI; Blob in useRef only; never in console/storage/URL.
- **Gates Touched:** G1, G2, G3, G4, G5, G6, G7
- **Affected Layers:** atoms (RecordButton), molecules (VoiceCapture), hooks (useVoiceCapture), services (transcribe), app (draft page), lib (constants)

---

## Draft page auto-sync to finalized state (FE-010)

- **Goal:** Fix the draft-page UX bug where a fresh navigation to `/encounters/{id}/draft` for an encounter with existing `record_final` rows renders the input form instead of the finalized-state UI. After this Block, the page MUST detect existing finals on mount and render the same finalized UI that `lifecycle.approve()` produces — preventing accidental re-generation over a signed chart.
- **Inputs:**
  - frontend/SPEC.md#draft-page-finalized-auto-sync — full acceptance criteria
  - frontend/SPEC.md#ai-output-patterns — finalized-state visual contract (badge, AIIndicatedText `ariaLabel="確定カルテ"`, ChainList)
  - frontend/src/services/finals.ts — existing `listFinalsByEncounter` (reused as-is)
  - frontend/src/hooks/useEncounterDrafts.ts — architectural template for new `useEncounterFinals`
  - frontend/src/hooks/useDraftLifecycle.ts — extension target for `initialFinal` parameter
  - frontend/src/hooks/useFinalChain.ts — reused unchanged
  - frontend/src/app/encounters/[encounterId]/draft/page.tsx — extension target
  - frontend/src/app/encounters/[encounterId]/draft/**tests**/page.test.tsx — extension target
  - .claude/rules/local-llm-and-phi.md §3, §4 — final.content is PHI
- **Acceptance:**
  - [ ] `src/hooks/useEncounterFinals.ts` exports `useEncounterFinals()` returning `{ status, finals, latest, error, load }`. AbortController per call; AbortError silently swallowed.
  - [ ] `src/hooks/__tests__/useEncounterFinals.test.ts` — ≥5 unit tests per SPEC acceptance.
  - [ ] `src/hooks/useDraftLifecycle.ts` extended: optional `initialFinal?: RecordFinal | null`. When non-null on first render → `mode="finalized"` + latch.
  - [ ] `src/hooks/__tests__/useDraftLifecycle.test.ts` extended: ≥3 new tests. Existing FE-004/005 tests stay green.
  - [ ] `src/app/encounters/[encounterId]/draft/page.tsx` extended: calls `useEncounterFinals.load(encounterId)` in parallel with `useEncounterDrafts.load`; passes `latest` into `useDraftLifecycle` as `initialFinal`; loading indicator covers both fetches; suppresses draft auto-seed when finals exist.
  - [ ] `src/app/encounters/[encounterId]/draft/__tests__/page.test.tsx` extended: `renderPage` signature gains 6th optional override for `useEncounterFinals`; new `describe("DraftPage (FE-010: finalized auto-sync on mount)")` with ≥4 tests covering the four edge cases.
  - [ ] Cross-cutting: 0 `fetch(` in components/app; 0 storage writes; 0 `console.*`; 0 `: any`; no raw HTML; no new heavy dep.
  - [ ] No FE-003..009 regression: full test suite passes.
  - [ ] G1 `npx tsc --noEmit` clean; G2 `npx eslint . && npx prettier --check .` clean; G3 `npm test -- --run` all pass; net count > 353.
  - [ ] G4 security-check skill invoked; PHI handling verified.
- **Out-of-scope:** Server-pushed revalidation; non-head final selection; sibling encounter finals; user-visible error on finals fetch fail; refactoring useEncounterDrafts/useEncounterDetail; combining drafts/finals into single hook; backend changes; cost-check (no inference).
- **Open-questions:** _(none)_
- **Inference Impact:** no
- **Data Sensitivity:** PHI; `RecordFinal.content` rendered per `.claude/rules/local-llm-and-phi.md` §4. Identical handling to FE-006's chain rendering.
- **Gates Touched:** G1, G2, G3, G4, G6, G7
- **Affected Layers:** hooks (new `useEncounterFinals`, extended `useDraftLifecycle`), app (draft page extension)

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
