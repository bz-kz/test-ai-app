# Frontend SPEC

Sub-spec for the Next.js (15+) / TypeScript / Tailwind frontend. Extends, never overrides, the root `SPEC.md`. All sections below are Blocks per `docs/handoff-contract.md`.

## Frontend Mission

- **Goal:** Provide clinicians a calm, accessible UI to draft, review, and finalise medical records, with AI output clearly distinguished from clinician-authored text.
- **Inputs:**
  - SPEC.md#product-goal
  - DESIGN.md — visual language, AI Output Patterns, Accessibility Bar
- **Acceptance:**
  - [ ] Every page renders with no console errors at WCAG 2.2 AA.
  - [ ] Every AI-rendered text block carries the AI Indicator from DESIGN.md.
  - [ ] No PHI is written to `localStorage`, `sessionStorage`, or IndexedDB.
- **Out-of-scope:** Native mobile, offline-first, multi-window editing.
- **Open-questions:** _(none)_
- **Data Sensitivity:** PHI

## Atomic Design Mapping

- **Goal:** Lock the placement rule for components so the Generator never has to guess where new code goes.
- **Inputs:**
  - DESIGN.md#atomic-design-mapping
- **Acceptance:**
  - [ ] Atoms (`src/components/atoms/`): Button, Input, Chip, Checkbox, RadioButton, Tooltip, Badge.
  - [ ] Molecules (`src/components/molecules/`): FormField (label + Input + helper/error), LabValueRow, AIIndicatedText, MaskToggle, ConfidencePill.
  - [ ] Organisms (`src/components/organisms/`): RecordDraftEditor, RecordList, EncounterPanel, InferenceProgress.
  - [ ] No data-fetching inside components. API calls live in `src/services/`; React state and lifecycle in `src/hooks/`.
  - [ ] Constants (model variant strings, latency thresholds, status colours) centralised in `src/lib/constants.ts`.
- **Out-of-scope:** Templates layer (the project does not introduce one until needed).
- **Open-questions:** _(none)_
- **Gates Touched:** G7
- **Affected Layers:** atoms, molecules, organisms

## AI Output Patterns

- **Goal:** Ensure every Gemma-generated string is unambiguously distinguished from clinician-authored text and offers Regenerate / Edit / Approve actions.
- **Inputs:**
  - DESIGN.md#ai-output-patterns
  - SPEC.md#inference-layer-contract
- **Acceptance:**
  - [ ] AI-generated text uses `<AIIndicatedText>` (left border + AI icon).
  - [ ] Streaming responses show a caret cursor; the cursor is removed on stream completion.
  - [ ] Each AI block exposes Regenerate (primary repeat), Edit (inline), and Approve (commits to record_draft → record_final flow).
  - [ ] Confidence ≤0.5 from the model is surfaced via `<ConfidencePill variant="warning">`.
- **Out-of-scope:** Per-token highlighting, model-explanation overlays.
- **Open-questions:** _(none)_
- **Inference Impact:** yes; UI consumes the streaming endpoint.
- **Gates Touched:** G6, G7

## Latency UX Budget

- **Goal:** Match user-visible feedback to local Gemma's response shape so the UI never appears stalled.
- **Inputs:**
  - DESIGN.md#inference-latency-ux
  - SPEC.md#hardware-assumptions
- **Acceptance:**
  - [ ] ≤300 ms: no visible loading state.
  - [ ] 300 ms–1 s: subtle spinner inside the action.
  - [ ] 1–3 s: skeleton in the target output area.
  - [ ] 3–10 s: skeleton + textual hint ("ローカルモデル応答待ち").
  - [ ] > 10 s: cancel button appears; on cancel, the request aborts and the UI returns to idle.
- **Out-of-scope:** Background prefetch, speculative generation.
- **Open-questions:** _(none)_
- **Gates Touched:** G5, G6

## Default Gates

Every frontend feature task sets at minimum: `Gates Touched: G1, G2, G3, G6, G7`. Add G4 for any task that displays PHI fields, G5 for any task with inference UI, G0 for changes that touch `docker-compose.yml` or the dev container.

## Layer rules (recap)

- Pages (`src/app/...`) compose organisms and call hooks; they MUST NOT call `fetch` directly.
- Hooks (`src/hooks/`) own client state and side effects; they call services, never `fetch`.
- Services (`src/services/`) are the only callers of `fetch`. They handle URL, auth, and error normalisation.
- No `any`. Use `unknown` and narrow at the boundary.
