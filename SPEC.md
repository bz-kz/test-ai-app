# SPEC: AI Medical Record Generator

Project-level specification. Sub-specs in `frontend/SPEC.md` and `backend/SPEC.md` extend this document. All Blocks below conform to `docs/handoff-contract.md`.

## Product Goal

- **Goal:** Help a clinician draft, review, and finalise medical records faster by generating structured drafts from raw clinical input using a locally-hosted Gemma 4 E4B model. The clinician is always the editor of last resort; the system never auto-finalises a record.
- **Inputs:**
  - DESIGN.md — visual language and AI-output patterns
  - CLAUDE.md — coding standards and harness flow
- **Acceptance:**
  - [ ] A draft can be generated from a clinical-note prompt within the latency budget below.
  - [ ] The clinician can edit, regenerate, or reject any AI output before it is saved.
  - [ ] No PHI ever leaves the local Docker network.
- **Out-of-scope:** Multi-tenant deployment, cloud LLM fallback, billing/EHR integration, mobile-native client.
- **Open-questions:** _(none — escalate via ADR if challenged)_
- **Data Sensitivity:** PHI

## Runtime Topology

- **Goal:** Pin the deployment shape so all sub-specs can reference one concrete environment.
- **Inputs:**
  - docs/runbook-local-dev.md — operational steps for the same topology
- **Acceptance:**
  - [ ] Single `docker-compose.yml` runs frontend, backend, postgres, llm.
  - [ ] Only `frontend` (3000) and `backend` (8000) publish ports to the host.
  - [ ] `llm` and `postgres` are reachable only on the internal compose network.
  - [ ] `docker compose up -d` brings the system to healthy in ≤120 s on a developer machine after first boot.
- **Out-of-scope:** Production orchestration (k8s/Nomad/etc.).
- **Open-questions:** _(none)_
- **Gates Touched:** G0

## Inference Layer Contract

- **Goal:** Fix the API and behaviour the backend assumes from the local LLM service so it can be implemented, mocked, and replaced without touching consumers.
- **Inputs:**
  - .claude/rules/local-llm-and-phi.md — non-negotiable boundaries
- **Acceptance:**
  - [ ] Interface `LocalLLMClient` lives in `backend/app/infrastructure/llm/` with `generate(prompt, params) -> Response` and `stream(prompt, params) -> Iterator[Chunk]`.
  - [ ] Concrete `OllamaLocalLLMClient` targets `http://llm:11434` and the model name from configuration.
  - [ ] Test-only `FakeLocalLLMClient` is the default in unit tests.
  - [ ] Single supported model: `gemma4:e4b` (Gemma 4 E4B). The model name is read from configuration (`LLM_MODEL`), never hardcoded; switching variants requires an ADR.
  - [ ] Timeout default: 60 s for `generate`, 120 s end-to-end for `stream`. Cancellable.
  - [ ] On non-200 or timeout, the client raises a typed `InferenceError` carrying a masked context, never the raw prompt.
- **Out-of-scope:** Multi-model routing, embeddings (separate Spec), function-calling.
- **Open-questions:** _(none)_
- **Inference Impact:** yes; system prompt is medical-record-drafting; expected prompt length ≤4k tokens, expected output ≤1.5k tokens.
- **Data Sensitivity:** PHI; clients MUST mask before logging.
- **Gates Touched:** G4, G5, G7
- **Affected Layers:** infrastructure, usecases

## ASR Layer Contract

- **Goal:** Fix the API and behaviour the backend assumes from the local ASR service so voice input can be implemented, mocked, and replaced without touching consumers, on the same shape as `#inference-layer-contract` for the LLM. As of 2026-05-12 (ADR-0003) the contract has two variants — a non-streaming variant (default) and an opt-in streaming variant gated behind an env-var flag; both share the same `LocalASRClient` interface and underlying transcoder.
- **Inputs:**
  - docs/adr/0001-voice-input-and-local-asr.md — variant pick, hardware footprint, network boundary.
  - docs/adr/0003-streaming-asr-chunked.md — chunked-streaming approach, env-var rollback, latency profile.
  - .claude/rules/local-llm-and-phi.md — non-negotiable boundaries; audio/voice extension lands once ADR-0001 is `Accepted`.
- **Acceptance:**
  - [ ] Interface `LocalASRClient` lives in `backend/app/infrastructure/asr/` with `transcribe(audio: AudioPayload, params: TranscribeParams | None) -> TranscribeResponse` for the non-streaming path AND `stream_transcribe(audio: AudioPayload, params: TranscribeParams | None) -> AsyncIterator[TranscribeChunk]` for the streaming path. Both methods MUST coexist on every implementation; tests inject `FakeLocalASRClient` which serves both.
  - [ ] `TranscribeChunk` is a frozen dataclass exporting `text: str`, `chunk_index: int` (0-based), `chunk_count: int` (total chunks the implementation will produce; -1 if unknown until completion), and `done: bool`. `done=True` chunks carry the final assembled text in `text` (mirroring `Chunk(text=..., done=True)` from `#inference-layer-contract`).
  - [ ] Concrete `WhisperCppLocalASRClient` targets `http://asr:8080` (whisper-server default) and the model name from configuration; configuration values `ASR_BASE_URL`, `ASR_MODEL`, `ASR_TIMEOUT_S` are read from environment, never hardcoded.
  - [ ] Test-only `FakeLocalASRClient` is the default in unit tests; deterministic outputs from a fixture map keyed by input-bytes hash. The fake's `stream_transcribe` yields the same fixture text in N synthetic chunks (default 3), with a configurable per-chunk delay so timing-sensitive tests can drive the latency tiers deterministically.
  - [ ] Single supported variant: `whisper.cpp medium-q5_0` GGML. Switching variants (e.g. to `kotoba-whisper-v2.0-ggml`) requires a follow-up ADR per ADR-0001's `ASR_MODEL` discipline.
  - [ ] Non-streaming timeout default: `ASR_TIMEOUT_S=90` (cover RTF ≤1.5× of a 60 s clip on the reference CPU). Cancellable via `asyncio.Task.cancel()`.
  - [ ] Streaming chunk-size default: `ASR_STREAM_CHUNK_SECONDS=10` (range 5–20; values outside the range MUST raise a configuration error at startup). Streaming per-chunk timeout reuses `ASR_TIMEOUT_S=90`; streaming end-to-end timeout: `ASR_STREAM_TOTAL_TIMEOUT_S=180` bounds the whole generator lifecycle and MUST trigger a streaming `ASRError(timeout=True)` if exceeded.
  - [ ] Streaming chunk-overlap: 0 seconds in v1; overlap is explicitly an out-of-scope follow-up enhancement (see Out-of-scope below).
  - [ ] First-chunk latency target for the streaming path: p95 ≤25 s (`ASR_STREAM_FIRST_CHUNK_LATENCY_S=25`) measured from the moment the chunked PCM data is ready to the moment the first SSE `data:` frame is flushed. Total wall-clock for a 60 s clip via streaming: p95 ≤180 s.
  - [ ] Accepted input: WebM/Opus container, single channel, ≤60 s wall-clock duration, ≤2 MB payload. Backend transcodes to 16 kHz mono 16-bit PCM WAV before any inference call (BE-016); streaming path slices the resulting PCM data into chunk-second segments and rebuilds a WAV header per segment using only Python's standard `wave` module — no new heavy dep.
  - [ ] On non-200 or timeout for either path, the client raises a typed `ASRError` carrying a masked context, never the raw audio bytes or transcript. `ASRError` mirrors the `InferenceError` discipline from `#inference-layer-contract`. Streaming mid-stream errors propagate through the async iterator and are mapped to SSE `event: error` frames at the interface layer (mirroring BE-013).
  - [ ] Audio bytes are never persisted to disk past the request lifetime. The backend MUST use `tempfile.SpooledTemporaryFile` (in-memory below threshold; auto-deleted otherwise) or stream the multipart body straight to the ASR client without writing to a named file. The chunk-segmentation step MUST operate in-memory only; chunked PCM byte slices MUST NOT be written to named files.
  - [ ] Rollback gate (binding): the streaming path is opt-in via the frontend env var `NEXT_PUBLIC_ASR_STREAMING_ENABLED` (default `"false"`). When `"false"` the frontend MUST consume only the non-streaming `POST /encounters/{id}/transcribe` endpoint; the backend MUST continue to serve that endpoint unchanged. The streaming endpoint `POST /encounters/{id}/transcribe/stream` is additive — removing it does not break any caller when the flag is `"false"`. Flipping the flag to `"false"` MUST restore BE-016 behaviour without a code change.
- **Out-of-scope:**
  - Parallel chunk processing — whisper.cpp serializes inference, so concurrent calls would queue server-side anyway and add no real throughput.
  - Real-time microphone → whisper continuous streaming (different audio-capture paradigm; needs WebSocket or MediaRecorder timeslice → fetch-multiplexer; would require a separate ADR).
  - Chunk overlap (non-zero); revisit after first streaming cut ships and word-boundary corruption is measured on real recordings.
  - Diarization, multi-speaker separation, speaker identification.
  - Language other than Japanese.
  - Transcript versioning, transcript persistence on the backend (the frontend appends to `clinical_input` and discards on submit).
  - kotoba-whisper variant swap (separate ADR per ADR-0001).
  - Partial-result commits to textarea on mid-stream cancel/error (see `frontend/SPEC.md#voice-capture` for the binding rule: cancel/error discards accumulated chunks).
- **Open-questions:** _(none — ADR-0003 closes them)_
- **Inference Impact:** yes; ASR is a second inference path with its own model and latency budget. Compute budget independent of LLM but co-resident. Streaming variant adds per-chunk dispatch overhead but does not add a second model load — sequential calls reuse the loaded whisper.cpp medium-q5_0 weights.
- **Data Sensitivity:** PHI; audio bytes are PHI per ADR-0001 and `.claude/rules/local-llm-and-phi.md` §3. Clients MUST mask any logged reference to audio length, transcript, or filename. Audio bytes MUST NOT appear in logs, error envelopes, stack traces, SSE frame payloads (only the masked transcript text travels over SSE — see BE-013 precedent), or any persistence layer. Chunked PCM byte slices are PHI on the same footing as the parent audio.
- **Gates Touched:** G0, G4, G5, G7
- **Affected Layers:** infrastructure, usecases

## Hardware Assumptions

- **Goal:** State the baseline so latency and memory budgets in feature Specs are interpretable.
- **Inputs:**
  - docs/adr/0001-voice-input-and-local-asr.md — co-resident `asr` service raises the Docker memory floor.
- **Acceptance:**
  - [ ] Reference dev hardware: 8-core CPU, 24 GB system RAM with Docker Desktop allocated ≥13 GB to cover `llm` + `asr` co-resident on the internal network, optional single GPU with ≥10 GB VRAM (e.g. RTX 4070) when offload is available. 16 GB Docker allocation is recommended for headroom and for the kotoba-whisper variant swap path described in ADR-0001.
  - [ ] CPU-only operation supported on the reference RAM allocation above; latencies SHOULD assume ≥3× slowdown vs GPU baseline for `gemma4:e4b`, and the ASR RTF budget in `#asr-layer-contract` applies independently.
  - [ ] Latency budget for `gemma4:e4b` first-token: p95 ≤1 s; total response p95 ≤6 s for 1k output tokens.
  - [ ] Memory footprint of the publisher-supplied `gemma4:e4b` Ollama tag: ≈10 GiB total system memory at runtime (≈9.4 GiB weights + ≈224 MiB KV cache + ≈125 MiB compute graph). The tag is loaded at its publisher-supplied default precision; the project pins this tag and does NOT assume a Q4_0 (or any other) re-quantization. A custom Modelfile to re-quantize is out-of-scope and would require an ADR.
  - [ ] Memory footprint of the pinned ASR variant (`whisper.cpp medium-q5_0` GGML, default): ≈0.7–0.9 GiB resident at idle, peak ≈1.0 GiB during a single 60 s clip. Co-resident total budget (gemma 10 GiB + ASR 1 GiB + backend/postgres/frontend/Docker overhead 2 GiB) = ≈13 GiB; this is the floor for the Docker Desktop memory slider.
  - [ ] On a machine with no GPU or insufficient VRAM, the same footprint is paid in system RAM rather than VRAM; the Docker Desktop memory allocation MUST be sized for the larger of the two cases.
- **Out-of-scope:** Multi-GPU, Apple-Silicon-specific tuning (track in a follow-up ADR if needed), custom Modelfile re-quantization of `gemma4:e4b`, ASR variants other than the one pinned by ADR-0001.
- **Open-questions:** _(none)_
- **Gates Touched:** G5

## Domain Glossary (medical)

- **Goal:** Lock the canonical names so frontend, backend, and prompt templates do not drift.
- **Inputs:** _(none)_
- **Acceptance:**
  - [ ] Each term below has exactly one canonical English identifier and one Japanese display label.
- **Out-of-scope:** Non-listed terms; add via ADR.
- **Open-questions:** _(none)_

| Concept            | Identifier (code/API) | Display (JP) | Notes                                  |
| ------------------ | --------------------- | ------------ | -------------------------------------- |
| Patient            | `patient`             | 患者         | Subject of a record.                   |
| Medical Record No. | `mrn`                 | 診察番号     | Stable identifier; PHI.                |
| Encounter          | `encounter`           | 受診         | One clinical visit; parent of records. |
| Record Draft       | `record_draft`        | カルテ下書き | AI-generated, unsigned.                |
| Record Final       | `record_final`        | 確定カルテ   | Clinician-signed, immutable.           |
| Clinician          | `clinician`           | 医師         | Authoring user.                        |
| Lab Value          | `lab_value`           | 検査値       | Numeric observation; tabular display.  |
| AI Confidence      | `confidence`          | 信頼度       | Optional model-reported score.         |

## Cross-cutting Constraints

- **Language:** Code identifiers and API fields in English. UI labels in Japanese. Code comments in Japanese (per CLAUDE.md). Docs in English.
- **Type safety:** No `any` (TS) and no untyped dicts crossing layer boundaries (Python). Pydantic at every interface boundary.
- **Architecture:** Frontend is Atomic Design over an Onion-style logic split (services/hooks). Backend is DDD with `domain → usecases → infrastructure → interfaces`.
- **PHI:** Governed by `.claude/rules/local-llm-and-phi.md`. Masked in logs, never persisted in browser storage, never sent to a hosted LLM. Audio/voice recordings of patient narrative are PHI on the same footing as `clinical_input` and `draft.content` (binding once ADR-0001 is `Accepted` and §3 is updated).
- **ASR egress:** All ASR calls flow `frontend → backend → asr` on the internal compose network. The browser MUST NOT call any ASR endpoint directly. The Web Speech API and any hosted-ASR SDK are forbidden by the same egress reasoning that already forbids hosted LLM SDKs (see ADR-0001).
- **Authentication:** Every PHI-returning endpoint requires the `X-Clinician-Id` header per the Authentication (PoC) Block. Production-grade auth is a separate Block.
- **Determinism for tests:** All inference paths use `FakeLocalLLMClient` in unit tests; ASR paths use `FakeLocalASRClient`. Integration tests against the real `llm` / `asr` containers are tagged and excluded from the default `pytest`/`vitest` run.

## Authentication (PoC)

- **Goal:** Satisfy `.claude/rules/local-llm-and-phi.md` §4 "operational reads stay unmasked but are gated by usecase-level authorisation" by introducing a minimal, replaceable clinician-identification scheme suitable for a local-only PoC. The scheme establishes a load-bearing identifier for audit + authorisation gates; it is NOT a credential-verification system.
- **Inputs:**
  - .claude/rules/local-llm-and-phi.md §4 — usecase-level authorisation requirement
  - CLAUDE.md §2 — local-only PoC scope (no remote / staging / production)
  - backend/SPEC.md#api-surface — existing error envelope `{ "code": str, "message": str }`
- **Acceptance:**
  - [ ] Every PHI-returning HTTP endpoint requires the request to carry an `X-Clinician-Id: <uuid>` header. The header value MUST parse as a v4 UUID; the backend trusts the header verbatim and does NOT verify a signature, session, or password.
  - [ ] Missing or malformed `X-Clinician-Id` returns 401 with the error envelope `{ "code": "unauthenticated", "message": "Clinician identification required." }`. The 401 message MUST NOT echo the offending header value, request body, or any PHI.
  - [ ] Endpoints that do NOT return PHI — `/health`, `/ping`, `/openapi.json` — do NOT require the header and continue to respond unchanged.
  - [ ] The header-derived UUID is the value written to `audit_log.actor` for every PHI-mutating action (patient create, encounter create, draft create/edit/finalize, final correct). It replaces every existing use of `_PLACEHOLDER_CLINICIAN_ID`.
  - [ ] No request-body field named `clinician_id` is accepted on any endpoint after this Block ships; with `extra='forbid'`-style Pydantic configs already in place, sending `clinician_id` in the body MUST return 422.
  - [ ] The frontend MUST attach the `X-Clinician-Id` header on every PHI-returning fetch call routed through `src/services/*`. The header value lives in memory only — never in `localStorage`, `sessionStorage`, or `IndexedDB`, consistent with `frontend/SPEC.md#frontend-mission`.
  - [ ] The header is logged through the existing masking pipeline (`mask_phi` / `short_id`); raw UUIDs do not appear at INFO level.
- **Out-of-scope:**
  - Authentication provider integration (SSO, OAuth2/OIDC, SAML).
  - JWT issuance, JWT verification, JWKS rotation.
  - Password storage, password reset, MFA, WebAuthn.
  - Role-based authorisation beyond clinician identity (e.g. admin/auditor splits).
  - Session management, refresh tokens, logout.
  - CSRF protection, rate limiting per clinician, account lockout.
  - mTLS or transport-level identity binding.
  - Replacing the header scheme with a production design — that requires a separate Spec Block and ADR.
- **Open-questions:** _(none — header-trust PoC is intentional; production-grade auth is explicitly a follow-up Block)_
- **Inference Impact:** no
- **Data Sensitivity:** PHI; the clinician UUID itself is treated as identifying data and logged only through `short_id(...)` at INFO level per `.claude/rules/local-llm-and-phi.md` §3.
- **Gates Touched:** G1, G2, G3, G4, G6, G7

## Living index

- Frontend Spec: `frontend/SPEC.md`
- Backend Spec: `backend/SPEC.md`
- Handoff contract: `docs/handoff-contract.md`
- Definition of Done & Gates: `docs/dod-and-gates.md`
- Local-dev runbook: `docs/runbook-local-dev.md`
- ADR index: `NOTES.md`
- PHI/LLM rule: `.claude/rules/local-llm-and-phi.md`
- Voice/ASR decision: `docs/adr/0001-voice-input-and-local-asr.md`
