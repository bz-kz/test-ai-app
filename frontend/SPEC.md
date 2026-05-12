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
  - docs/adr/0001-voice-input-and-local-asr.md — voice-input scope
- **Acceptance:**
  - [ ] Atoms (`src/components/atoms/`): Button, Input, Chip, Checkbox, RadioButton, Tooltip, Badge, RecordButton.
  - [ ] Molecules (`src/components/molecules/`): FormField (label + Input + helper/error), LabValueRow, AIIndicatedText, MaskToggle, ConfidencePill, VoiceCapture.
  - [ ] Organisms (`src/components/organisms/`): RecordDraftEditor, RecordList, EncounterPanel, InferenceProgress.
  - [ ] No data-fetching inside components. API calls live in `src/services/`; React state and lifecycle in `src/hooks/`.
  - [ ] Constants (model variant strings, latency thresholds, status colours, audio-capture limits) centralised in `src/lib/constants.ts`.
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

## Voice Capture

- **Goal:** Let a clinician dictate the Subjective/Objective narrative on `/encounters/[encounterId]/draft` and append the resulting Japanese transcript to the existing `clinical_input` textarea, without any audio leaving the local Docker network. The transcript becomes editable text; the clinician edits in place before generating the draft. As of FE-013 (2026-05-12), the molecule supports two code paths — a non-streaming path (default, BE-014/016) and an opt-in streaming path (BE-017) gated by `NEXT_PUBLIC_ASR_STREAMING_ENABLED`. The streaming path renders progressive feedback inside the molecule's aria-live region but only commits the final assembled transcript to the parent textarea atomically on completion.
- **Inputs:**
  - SPEC.md#asr-layer-contract — backend wire contract; streaming variant + rollback flag
  - docs/adr/0001-voice-input-and-local-asr.md — variant pick + PHI extension
  - docs/adr/0003-streaming-asr-chunked.md — streaming approach, env-var rollback, latency profile
  - backend/SPEC.md#transcribe-endpoint — non-streaming endpoint contract
  - backend/SPEC.md#transcribe-streaming-endpoint — streaming endpoint contract; SSE envelope identical to BE-013
  - frontend/SPEC.md#frontend-mission — PHI in browser storage prohibited
  - frontend/SPEC.md#layer-rules — services own fetch
  - frontend/src/services/drafts.ts — `streamRecordDraft` (FE-008) is the precedent SSE consumer; the streaming transcribe service reuses the same frame-parsing structure mechanically
  - DESIGN.md#accessibility-bar — focus ring + reduced-motion contract
- **Acceptance:**
  - [ ] Atom `RecordButton` (`src/components/atoms/RecordButton.tsx`) — unchanged from FE-009: two visual states (`idle`, `recording`), 48 × 48 px hit area, `aria-pressed`, `aria-label` `"録音を開始"` / `"録音を停止"`. No new atom state introduced for streaming.
  - [ ] Molecule `VoiceCapture` (`src/components/molecules/VoiceCapture.tsx`): composes `RecordButton` + elapsed-seconds counter + transcription-status text. Owns the `MediaRecorder` lifecycle: `getUserMedia({ audio: { channelCount: 1 } })` on first record press; releases the `MediaStream` (`.getTracks().forEach(t => t.stop())`) on stop, on unmount, and on error. Recording auto-stops at 60 seconds (matches `SPEC.md#asr-layer-contract` payload ceiling) with a JP toast `"録音は60秒で停止しました"`.
  - [ ] Recording produces a single `Blob` with MIME `audio/webm;codecs=opus` (the only codec the backend accepts per `backend/SPEC.md#transcribe-endpoint`). The Blob lives in component state only — never written to `localStorage`, `sessionStorage`, `IndexedDB`, or `URL.createObjectURL` references that survive the upload.
  - [ ] On stop, `VoiceCapture` calls a parent `onTranscript(text)` callback with the returned final transcript. The parent (the draft page) appends the transcript to the existing `clinical_input` textarea separated by a newline; it does NOT replace what the clinician already typed. The Blob reference is dropped immediately after the upload promise (non-stream) or stream-complete callback resolves or rejects.
  - [ ] Service `src/services/transcribe.ts` exports both `transcribeAudio(encounterId, blob, opts?) -> TranscribeResult` (non-stream, FE-009 behaviour preserved unchanged) AND `streamTranscribeAudio(encounterId, blob, opts) -> Promise<void>` (FE-013). The streaming function takes callbacks `onChunk(text, chunkIndex, chunkCount)`, `onComplete({fullText, durationSeconds, chunkCount})`, `onError({kind, chunkIndex?})` mirroring the `streamRecordDraft` shape from FE-008. The streaming function uses raw `fetch` (apiFetch does not support multipart + SSE) and parses SSE frames using the same `\n\n` + `event:` / `data:` envelope as `streamRecordDraft`. No PHI in logs; chunk text never console-logged; Blob reference not logged.
  - [ ] Hook `src/hooks/useVoiceCapture.ts` owns the state machine: `idle | requesting_permission | recording | uploading | success | error | permission_denied`. The `uploading` state covers both non-streaming and streaming dispatch — the hook MUST NOT introduce a separate `streaming` status; instead the hook return shape gains an optional `streaming: { chunkIndex: number; chunkCount: number; partialText: string } | null` field that is non-null only when the streaming path is active and at least one chunk has arrived. The molecule subtype-narrows on this field to drive the progressive-feedback UI.
  - [ ] Feature-flag gating: a new constant `ASR_STREAMING_ENABLED = process.env.NEXT_PUBLIC_ASR_STREAMING_ENABLED === "true"` lives in `src/lib/constants.ts`; default `false`. The hook reads this constant ONCE at module scope and selects the dispatch function: `false` → `transcribeAudio` (existing behaviour), `true` → `streamTranscribeAudio` (FE-013 behaviour). Flipping the env var to `"false"` MUST restore BE-016 behaviour at next page load with no code change. Tests MUST cover both branches by mocking the constant.
  - [ ] Streaming progressive feedback (binding): while `streaming !== null`, the molecule's existing aria-live region renders `"文字起こし中… (チャンク {chunkIndex+1} / {chunkCount})"` for the screen-reader-friendly announcement, plus a read-only `<pre>` element (non-aria-live, max-height ~6 lines with `overflow-auto`) showing the accumulated partial transcript. The `<pre>` is purely visual; screen readers do not re-announce it on every chunk. The parent textarea is NOT touched during streaming.
  - [ ] Atomic textarea append: only on `onComplete` does the hook set `transcript = fullText`, transition to `status = "success"`, and clear `streaming`. The molecule's existing `success → onTranscript(text)` effect then fires once and appends the full text to the parent textarea. Mid-stream cancel or error MUST NOT call `onTranscript`.
  - [ ] Cancel semantics during streaming (binding): the existing cancel button (visible at >10 s elapsed, per `#voice-input-streaming-latency-ux`) calls the hook's `cancel()`, which (a) aborts the in-flight fetch via the existing AbortController, (b) clears `streaming` to `null`, (c) discards all accumulated chunks, (d) returns the hook to `idle`. No partial text is committed to the parent textarea.
  - [ ] Mid-stream error semantics (binding): when the SSE service callback `onError` fires (including codes `transcription_unavailable`, `transcription_timeout`), the hook sets `status = "error"` and chooses the JP error string from `VOICE_CAPTURE_ERRORS` exactly as the non-streaming path does. All accumulated chunks are discarded — no partial text is committed.
  - [ ] Microphone permission-denied path: unchanged from FE-009 — the hook surfaces `status: "permission_denied"` and the UI shows the static JP message.
  - [ ] Failure-mode UI strings (centralised in `src/lib/constants.ts`) — unchanged from FE-009 plus one new string:
    - permission denied: `"マイクへのアクセスが許可されていません。ブラウザ設定を確認してください。"`
    - upload aborted (user navigated away or cancelled): no toast; silent.
    - `transcription_unavailable`: `"音声の文字起こしサービスが一時的に利用できません。テキスト入力を使用してください。"`
    - `transcription_timeout`: `"音声が長すぎたか、サーバが混雑しています。録音を短くしてもう一度お試しください。"`
    - generic error: `"音声の文字起こしに失敗しました。"`
    - 60 s auto-stop toast: `"録音は60秒で停止しました"` (existing)
    - streaming-only progressive-feedback prefix (in `VOICE_CAPTURE_STATUS`): `"文字起こし中…"` (existing) + `"チャンク {n} / {m}"` derived (no new constant required)
  - [ ] Audio constraints constants in `src/lib/constants.ts` — unchanged: `AUDIO_MAX_DURATION_S = 60`, `AUDIO_MIME_TYPE = "audio/webm;codecs=opus"`, `AUDIO_MAX_BYTES = 2 * 1024 * 1024`.
  - [ ] Cross-cutting: 0 `fetch(` in components/app (raw fetch in the new service is permitted, same as `streamRecordDraft`); 0 storage writes; 0 `console.*`; 0 `: any`; 0 references to Web Speech API or `webkitSpeechRecognition`; the only browser API exercised is `MediaRecorder` + `navigator.mediaDevices.getUserMedia` + `fetch`'s `ReadableStream` reader.
  - [ ] No FE-009 regression: when `ASR_STREAMING_ENABLED === false`, all FE-009 behaviour (374 tests at FE-012) MUST remain green. The streaming code path adds new tests, never modifies existing ones.
- **Out-of-scope:**
  - Real-time microphone → backend continuous streaming (different audio-capture paradigm; would need WebSocket / MediaRecorder timeslice + server-side multiplexer; new ADR).
  - Replay / scrub of the recorded clip before upload.
  - Transcript preview-before-append (the textarea IS the preview).
  - Per-utterance language switching.
  - Transcript history, multi-clip queueing.
  - Batch transcription of older encounters.
  - Speaker diarization.
  - Transcript persistence on the frontend.
  - Committing partial transcripts to the parent textarea on mid-stream cancel or error (binding rule: full-or-nothing).
  - Re-rendering the cursor caret from `#ai-output-patterns` during streaming transcription — the caret is reserved for LLM streaming and would mislead the clinician.
  - Removing the non-streaming endpoint or the non-streaming code path — both are the rollback path.
- **Open-questions:** _(none — ADR-0003 closes them)_
- **Inference Impact:** yes; consumes either the non-streaming `POST /encounters/{id}/transcribe` (BE-014/016) or the streaming `POST /encounters/{id}/transcribe/stream` (BE-017) depending on the env-var flag. The page is already on the inference-touching path (it consumes `POST /encounters/{id}/drafts/stream`), so this adds a parallel inference channel.
- **Data Sensitivity:** PHI; audio bytes, chunk text, accumulated partial transcript, and final transcript are PHI per ADR-0001. Audio Blob lives in component memory only; partial transcript lives in `useRef` only per ADR-0004 (no React state for chunked text bodies that DevTools would snapshot); final transcript treated identically to `clinical_input` (never in console, never in storage, never in URL). Aria-live announcements use chunk-index counters only, never the transcript itself.
- **Gates Touched:** G1, G2, G3, G4, G5, G6, G7
- **Affected Layers:** molecules (extend VoiceCapture), hooks (extend useVoiceCapture), services (extend transcribe.ts — add `streamTranscribeAudio`), lib (extend constants — add `ASR_STREAMING_ENABLED`)

## Voice Input Latency UX

- **Goal:** Match user-visible feedback during transcription to whisper.cpp's CPU-bound response shape. Two tier-tables exist: the legacy non-streaming tiers (FE-009) and the new streaming tiers (FE-013). The molecule selects between them by reading `ASR_STREAMING_ENABLED`; both share the same `RecordButton` and aria-live region structure.
- **Inputs:**
  - frontend/SPEC.md#latency-ux-budget — five-tier baseline for LLM
  - SPEC.md#asr-layer-contract — `ASR_TIMEOUT_S=90`, RTF ≤1.5× on reference CPU; streaming targets `ASR_STREAM_FIRST_CHUNK_LATENCY_S=25` and `ASR_STREAM_TOTAL_TIMEOUT_S=180`
  - docs/adr/0003-streaming-asr-chunked.md — streaming latency rationale
  - DESIGN.md#inference-latency-ux — base latency vocabulary
- **Acceptance:**
  - [ ] Non-streaming tiers (FE-009, preserved unchanged when `ASR_STREAMING_ENABLED === false`). During `uploading` status:
    - [ ] ≤500 ms: no visible loading state beyond the `RecordButton`'s post-stop state change.
    - [ ] 500 ms – 3 s: a small spinner inside the `VoiceCapture` molecule replaces the elapsed-seconds counter; text reads `"文字起こし中…"`.
    - [ ] 3 s – 10 s: the spinner stays; the text gains a secondary hint `"ローカル音声認識の応答待ち"`.
    - [ ] > 10 s: a Cancel button (Secondary, sm) appears next to the spinner; on cancel the AbortController aborts the upload and the UI returns to `idle` with no toast.
    - [ ] On hard timeout from the server (504 `transcription_timeout`) the UI shows the centralised JP timeout string and returns to `idle`.
  - [ ] Streaming tiers (FE-013, active when `ASR_STREAMING_ENABLED === true`). During `uploading` status with `streaming === null` (no chunk has arrived yet):
    - [ ] ≤500 ms: no visible loading state beyond the `RecordButton`'s post-stop state change.
    - [ ] 500 ms – 3 s: spinner + `"文字起こし中…"` text — same shape as the non-streaming 500ms–3s tier. The user does not yet know it is a streaming session.
    - [ ] 3 s – 10 s: spinner + `"文字起こし中…"` + secondary hint `"ローカル音声認識の応答待ち"` — same as non-streaming.
    - [ ] 10 s – `ASR_STREAM_FIRST_CHUNK_LATENCY_S` (25 s default): Cancel button (Secondary, sm) appears. No partial-transcript area yet.
    - [ ] > `ASR_STREAM_FIRST_CHUNK_LATENCY_S` with still no chunk: a tertiary hint `"応答に時間がかかっています"` appears below the spinner; Cancel remains visible. (Visual nag, not a hard error — the stream is still alive.)
  - [ ] Streaming tiers when `streaming !== null` (at least one chunk has arrived):
    - [ ] The spinner is replaced by a chunk-progress label: `"文字起こし中… (チャンク {chunkIndex + 1} / {chunkCount})"`. The aria-live region announces this label on each chunk so screen readers narrate progress.
    - [ ] A non-aria-live read-only `<pre class="max-h-32 overflow-auto whitespace-pre-wrap">` block shows the accumulated partial transcript visually. The block is BELOW the chunk-progress label and inside the same molecule (NOT inside the parent textarea). The label provides the screen-reader announcement; the `<pre>` is visual-only to avoid loud re-announcements of PHI.
    - [ ] The Cancel button remains visible throughout streaming; clicking it discards all chunks and returns the hook to `idle` (no `onTranscript` call).
    - [ ] On `event: complete`, the chunk-progress label briefly renders `"完了"` (≤500 ms), then `onTranscript(fullText)` fires once and the molecule returns to `idle`. The parent textarea atomically receives the full transcript.
  - [ ] Streaming caret semantics from `#ai-output-patterns` MUST NOT be used during transcription — even with streaming, the partial transcript is shown inside a static `<pre>`, not inline at an insertion point. Reusing the caret would imply continuous LLM-style emission, which is misleading for chunk-based ASR.
  - [ ] `prefers-reduced-motion`: spinner becomes a static "…" character and `RecordButton` pulse becomes a solid colour change. The streaming `<pre>` block does NOT animate scroll position changes when content is appended — it uses `scrollTop` only when motion-safe.
- **Out-of-scope:** Real-time mic → continuous streaming UX (different paradigm; see `#voice-capture` Out-of-scope). Audible feedback. Vibration feedback on mobile. Sub-chunk progress indication (e.g. "chunk 2 in progress" — granularity is per-chunk-complete).
- **Open-questions:** _(none — ADR-0003 closes them)_
- **Inference Impact:** yes; calibrates UX for the ASR streaming path.
- **Gates Touched:** G5, G6

## Draft Page Finalized Auto-Sync

- **Goal:** When a clinician navigates to `/encounters/[encounterId]/draft` for an encounter whose `record_final` table already contains at least one row, the page MUST render the finalized-state UI on mount — not the input form. This is the same finalized-state UI that the page reaches via `lifecycle.approve()` in the same session (確定済みバッジ + AIIndicatedText with `ariaLabel="確定カルテ"` + 訂正 Button + ChainList). The input textarea, voice capture, and "下書きを生成" button MUST be hidden in this mode. The fix is additive — the FE-006 auto-load path for drafts MUST continue to work unchanged for encounters that have drafts but no finals.
- **Inputs:**
  - frontend/SPEC.md#ai-output-patterns — finalized-state visual contract (badge, AIIndicatedText `ariaLabel="確定カルテ"`, ChainList)
  - frontend/src/services/finals.ts — existing `listFinalsByEncounter(encounterId)` returning `{ kind: "found"; finals: RecordFinal[] } | { kind: "error" }` (created in FE-007b)
  - frontend/src/hooks/useFinalChain.ts — takes `finalId`, not `encounterId`; reused unchanged
  - frontend/src/hooks/useEncounterDrafts.ts — existing FE-006 auto-load pattern serves as the architectural template
  - frontend/src/hooks/useDraftLifecycle.ts — current mode initialiser is `"view"`; needs a seed-from-finalized capability
  - backend `GET /encounters/{encounterId}/finals` — returns `RecordFinal[]` newest-first (BE-008/009 contract; `finals[0]` is the head)
  - .claude/rules/local-llm-and-phi.md §3, §4 — final content is PHI; no console/storage/URL writes
- **Acceptance:**
  - [ ] A new hook `src/hooks/useEncounterFinals.ts` exports `useEncounterFinals()` mirroring `useEncounterDrafts` shape: `status: "idle" | "loading" | "loaded" | "error"`, `finals: RecordFinal[]`, `latest: RecordFinal | null` (= `finals[0] ?? null`), `error: string | null` (JP, PHI-free), `load: (encounterId: string) => void`. AbortController per call. No PHI in logs.
  - [ ] `useDraftLifecycle` accepts a new optional parameter `initialFinal?: RecordFinal | null`. When `initialFinal` is non-null on first render, `mode` initialises to `"finalized"` and `final` initialises to that value; subsequent renders MUST NOT re-seed (latch via `useRef` boolean or lazy `useState` initialiser). When absent, behaviour is unchanged.
  - [ ] `src/app/encounters/[encounterId]/draft/page.tsx` is extended to:
    - Call `useEncounterFinals().load(encounterId)` on mount, in parallel with the existing `useEncounterDrafts.load(encounterId)` call.
    - Pass `useEncounterFinals.latest` to `useDraftLifecycle` as `initialFinal`.
    - While either fetch is `loading`, render the existing "下書きを確認しています…" indicator and render neither the input form nor the finalized UI.
    - Suppress the FE-006 drafts auto-seed (`setDraft(encounterDrafts.latest)`) when `encounterFinals.latest !== null`.
  - [ ] Edge-case rulings (binding):
    - (a) **Finals exist AND drafts exist** — finalized state wins. The page renders the finalized UI; drafts are ignored. Rationale: `record_final` is canonical; remaining drafts have been superseded.
    - (b) **Neither finals nor drafts** — current "下書きを生成" input-form path is preserved unchanged.
    - (c) **Drafts exist but no finals** — current FE-006 auto-load path is preserved unchanged.
    - (d) **Finals fetch fails (`status="error"`)** — silent fallback: the page proceeds as if no finals exist. No toast, no blocking error. Rationale matches FE-006's draft-fetch error treatment.
    - (e) **Cross-tab race (correction created in another tab while page open)** — out-of-scope for v1; refresh required.
  - [ ] `useEncounterFinals` MUST have ≥5 unit tests covering: (i) loaded+non-empty selects newest as `latest`; (ii) loaded+empty → `latest === null`; (iii) service error → `status="error"`; (iv) AbortController cancels in-flight call when `load` invoked twice; (v) AbortError silently swallowed.
  - [ ] `useDraftLifecycle` MUST have ≥3 new tests covering: (i) `initialFinal !== null` → `mode === "finalized"` on first render; (ii) `initialFinal === null` → existing `"view"` default preserved; (iii) `initialFinal` flips null→RecordFinal between renders → mode MUST NOT change (latch).
  - [ ] Page integration tests MUST cover the four edge cases on mount: (a) finals + drafts → finalized UI shown, input form NOT shown, `setDraft` NOT called; (b) neither → input form shown after both fetches settle; (c) drafts only → FE-006 auto-seed path still fires; (d) finals fetch errors → silent fallback.
  - [ ] Cross-cutting: 0 `fetch(` in components/app; 0 storage writes; 0 `console.*`; 0 `: any`; no raw HTML injection.
- **Out-of-scope:**
  - Server-pushed revalidation while the page is open (edge case (e) above).
  - Selecting a non-head final from the chain as `currentFinal` (head-only view).
  - Showing finals from sibling encounters.
  - Surfacing a user-visible error when finals fetch fails (silent fallback by SPEC ruling).
  - Refactoring `useEncounterDrafts` / `useEncounterDetail` to share a base hook.
  - Combining the drafts and finals fetches into a single hook on the draft page.
- **Open-questions:** _(none)_
- **Inference Impact:** no — this Block performs no inference calls; only DB-read GET endpoints.
- **Data Sensitivity:** PHI; `RecordFinal.content` is rendered in the operational-read path per `.claude/rules/local-llm-and-phi.md` §4. Never in `console.*`, `localStorage`/`sessionStorage`/`IndexedDB`, or URL. Masking discipline of FE-006 applies identically.
- **Gates Touched:** G1, G2, G3, G4, G6, G7
- **Affected Layers:** hooks (new `useEncounterFinals` + extended `useDraftLifecycle` signature), app (draft page extension)

## Default Gates

Every frontend feature task sets at minimum: `Gates Touched: G1, G2, G3, G6, G7`. Add G4 for any task that displays PHI fields, G5 for any task with inference UI, G0 for changes that touch `docker-compose.yml` or the dev container.

## Layer rules (recap)

- Pages (`src/app/...`) compose organisms and call hooks; they MUST NOT call `fetch` directly.
- Hooks (`src/hooks/`) own client state and side effects; they call services, never `fetch`.
- Services (`src/services/`) are the only callers of `fetch`. They handle URL, auth, and error normalisation.
- No `any`. Use `unknown` and narrow at the boundary.
