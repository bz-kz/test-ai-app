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

- **Goal:** Let a clinician dictate the Subjective/Objective narrative on `/encounters/[encounterId]/draft` and append the resulting Japanese transcript to the existing `clinical_input` textarea, without any audio leaving the local Docker network. The transcript becomes editable text; the clinician edits in place before generating the draft.
- **Inputs:**
  - SPEC.md#asr-layer-contract — backend wire contract
  - docs/adr/0001-voice-input-and-local-asr.md — variant pick + PHI extension
  - frontend/SPEC.md#frontend-mission — PHI in browser storage prohibited
  - frontend/SPEC.md#layer-rules — services own fetch
  - DESIGN.md#accessibility-bar — focus ring + reduced-motion contract
- **Acceptance:**
  - [ ] Atom `RecordButton` (`src/components/atoms/RecordButton.tsx`): two visual states — `idle` (microphone icon, Primary variant base) and `recording` (filled red dot + pulsing animation respecting `prefers-reduced-motion`); 48 × 48 px hit area at minimum; `aria-pressed` reflects recording state; `aria-label` is `"録音を開始"` in idle and `"録音を停止"` in recording. Disabled when the parent says so (e.g. while a transcription is in flight).
  - [ ] Molecule `VoiceCapture` (`src/components/molecules/VoiceCapture.tsx`): composes `RecordButton` + elapsed-seconds counter + transcription-status text. Owns the `MediaRecorder` lifecycle: `getUserMedia({ audio: { channelCount: 1 } })` on first record press; releases the `MediaStream` (`.getTracks().forEach(t => t.stop())`) on stop, on unmount, and on error. Recording auto-stops at 60 seconds (matches `SPEC.md#asr-layer-contract` payload ceiling) with a JP toast `"録音は60秒で停止しました"`.
  - [ ] Recording produces a single `Blob` with MIME `audio/webm;codecs=opus` (the only codec the backend accepts per `backend/SPEC.md#transcribe-endpoint`). The Blob lives in component state only — never written to `localStorage`, `sessionStorage`, `IndexedDB`, or `URL.createObjectURL` references that survive the upload.
  - [ ] On stop, `VoiceCapture` calls a parent `onTranscript(text)` callback with the returned transcript. The parent (the draft page) appends the transcript to the existing `clinical_input` textarea separated by a newline; it does NOT replace what the clinician already typed. The Blob reference is dropped immediately after the upload promise resolves or rejects.
  - [ ] Service `src/services/transcribe.ts` exports `transcribeAudio(encounterId, blob, opts?) -> TranscribeResult` using the existing `apiFetch` HTTP client pattern (multipart `FormData` body, `X-Clinician-Id` header attached by `apiFetch`). No PHI in logs; the Blob reference is not logged.
  - [ ] Hook `src/hooks/useVoiceCapture.ts` owns the state machine: `idle | requesting_permission | recording | uploading | success | error | permission_denied`. AbortController cancels in-flight upload on unmount. JP error strings centralised in `src/lib/constants.ts`.
  - [ ] Microphone permission-denied path: the hook surfaces `status: "permission_denied"` and the UI shows a static JP message `"マイクへのアクセスが許可されていません。ブラウザ設定を確認してください。"` next to the disabled `RecordButton`. Typing into the textarea remains fully functional — voice is additive, never required.
  - [ ] Failure-mode UI strings (centralised in `src/lib/constants.ts`):
    - permission denied: `"マイクへのアクセスが許可されていません。ブラウザ設定を確認してください。"`
    - upload aborted (user navigated away or cancelled): no toast; silent.
    - `transcription_unavailable` (503): `"音声の文字起こしサービスが一時的に利用できません。テキスト入力を使用してください。"`
    - `transcription_timeout` (504): `"音声が長すぎたか、サーバが混雑しています。録音を短くしてもう一度お試しください。"`
    - generic error: `"音声の文字起こしに失敗しました。"`
  - [ ] Audio constraints constants in `src/lib/constants.ts`:
    - `AUDIO_MAX_DURATION_S = 60`
    - `AUDIO_MIME_TYPE = "audio/webm;codecs=opus"`
    - `AUDIO_MAX_BYTES = 2 * 1024 * 1024` (2 MB; matches backend cap)
  - [ ] Cross-cutting: 0 `fetch(` in components/app; 0 storage writes; 0 `console.*`; 0 `: any`; 0 references to Web Speech API or `webkitSpeechRecognition`; the only browser API exercised is `MediaRecorder` + `navigator.mediaDevices.getUserMedia`.
- **Out-of-scope:** Streaming partial transcripts, replay/scrub of the recorded clip before upload, transcript preview-before-append (the textarea IS the preview), per-utterance language switching, transcript history, multi-clip queueing, batch transcription of older encounters, speaker diarization, transcript persistence on the frontend.
- **Open-questions:** _(none — ADR-0001 closes them)_
- **Inference Impact:** yes; consumes the backend ASR path via `POST /encounters/{id}/transcribe`. The page is already on the inference-touching path (it consumes `POST /encounters/{id}/drafts/stream`), so this adds a parallel inference channel.
- **Data Sensitivity:** PHI; audio bytes and the resulting transcript are PHI per ADR-0001. Audio Blob lives in component memory only; transcript is treated identically to `clinical_input` (never in console, never in storage, never in URL).
- **Gates Touched:** G1, G2, G3, G4, G5, G6, G7
- **Affected Layers:** atoms (RecordButton), molecules (VoiceCapture), hooks (useVoiceCapture), services (transcribe), lib (constants)

## Voice Input Latency UX

- **Goal:** Match user-visible feedback during transcription to whisper.cpp's CPU-bound response shape. The existing five-tier `#latency-ux-budget` is keyed off LLM streaming with continuous partial output; ASR has no partial output in v1, so the feedback shape differs.
- **Inputs:**
  - frontend/SPEC.md#latency-ux-budget — five-tier baseline for LLM
  - SPEC.md#asr-layer-contract — `ASR_TIMEOUT_S=90`, RTF ≤1.5× on reference CPU
  - DESIGN.md#inference-latency-ux — base latency vocabulary
- **Acceptance:**
  - [ ] During `uploading` status:
    - [ ] ≤500 ms: no visible loading state beyond the `RecordButton`'s post-stop state change.
    - [ ] 500 ms – 3 s: a small spinner inside the `VoiceCapture` molecule replaces the elapsed-seconds counter; text reads `"文字起こし中…"`.
    - [ ] 3 s – 10 s: the spinner stays; the text gains a secondary hint `"ローカル音声認識の応答待ち"` (analogous to the LLM `"ローカルモデル応答待ち"`).
    - [ ] > 10 s: a Cancel button (Secondary, sm) appears next to the spinner; on cancel the AbortController aborts the upload and the UI returns to `idle` with no toast.
    - [ ] On hard timeout from the server (504 `transcription_timeout`) the UI shows the centralised JP timeout string and returns to `idle`.
  - [ ] Streaming caret semantics from `#ai-output-patterns` MUST NOT be used during transcription — there is no partial transcript in v1. Reusing the caret would imply streaming and mislead the clinician.
  - [ ] `prefers-reduced-motion`: spinner becomes a static "…" character and `RecordButton` pulse becomes a solid colour change.
- **Out-of-scope:** Streaming partial transcripts (would require a separate Block + an ADR amendment), audible feedback, vibration feedback on mobile.
- **Open-questions:** _(none)_
- **Inference Impact:** yes; calibrates UX for the ASR path.
- **Gates Touched:** G5, G6

## Default Gates

Every frontend feature task sets at minimum: `Gates Touched: G1, G2, G3, G6, G7`. Add G4 for any task that displays PHI fields, G5 for any task with inference UI, G0 for changes that touch `docker-compose.yml` or the dev container.

## Layer rules (recap)

- Pages (`src/app/...`) compose organisms and call hooks; they MUST NOT call `fetch` directly.
- Hooks (`src/hooks/`) own client state and side effects; they call services, never `fetch`.
- Services (`src/services/`) are the only callers of `fetch`. They handle URL, auth, and error normalisation.
- No `any`. Use `unknown` and narrow at the boundary.
