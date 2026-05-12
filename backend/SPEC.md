# Backend SPEC

Sub-spec for the FastAPI / Python 3.12+ backend. Extends, never overrides, the root `SPEC.md`. All sections below are Blocks per `docs/handoff-contract.md`.

## Backend Mission

- **Goal:** Expose a typed HTTP API that lets the frontend manage patients, encounters, and AI-assisted record drafts, with all inference routed through a local Gemma 4 E4B service and PHI confined to the local Docker network.
- **Inputs:**
  - SPEC.md#product-goal
  - SPEC.md#inference-layer-contract
  - .claude/rules/local-llm-and-phi.md
- **Acceptance:**
  - [ ] All Request/Response bodies are Pydantic models.
  - [ ] No domain code imports from `infrastructure` or `usecases`.
  - [ ] No infrastructure code calls a hosted-LLM SDK; all inference goes through `app/infrastructure/llm/`.
  - [ ] Logs never contain unmasked PHI.
- **Out-of-scope:** Multi-tenant auth, cloud LLM fallback, message-queue async pipelines.
- **Open-questions:** _(none)_
- **Data Sensitivity:** PHI

## Layer Boundaries

- **Goal:** Pin the DDD direction so import-graph violations are mechanically detectable.
- **Inputs:** _(none)_
- **Acceptance:**
  - [ ] `app/domain/` — pure types and business invariants. No imports from any other `app/` package.
  - [ ] `app/usecases/` — orchestrates domain + infrastructure. May import from `domain` and `infrastructure`. MUST NOT be imported by `interfaces` directly except via the FastAPI dependency wiring.
  - [ ] `app/infrastructure/` — adapters: DB (SQLAlchemy), LLM (`LocalLLMClient`), external clients. MUST NOT import from `usecases` or `interfaces`.
  - [ ] `app/interfaces/` — FastAPI routers, request/response Pydantic models, dependency declarations. MUST NOT import from `infrastructure` directly; goes through `usecases`.
  - [ ] Direction (allowed): `interfaces → usecases → infrastructure → domain` (each layer may also depend on `domain`).
- **Out-of-scope:** Hexagonal-port abstractions beyond what `LocalLLMClient` requires.
- **Open-questions:** _(none)_
- **Gates Touched:** G7
- **Affected Layers:** domain, usecases, infrastructure, interfaces

## Inference Adapter

- **Goal:** Make the local-Gemma adapter a thin, replaceable component the rest of the backend talks to without knowing the wire format.
- **Inputs:**
  - SPEC.md#inference-layer-contract
  - .claude/rules/local-llm-and-phi.md
- **Acceptance:**
  - [ ] `app/infrastructure/llm/__init__.py` exports `LocalLLMClient` (Protocol/ABC).
  - [ ] `OllamaLocalLLMClient` implements it; talks to `http://llm:11434`.
  - [ ] `FakeLocalLLMClient` is the default in unit tests; deterministic outputs from a fixture map.
  - [ ] Configuration values (`LLM_BASE_URL`, `LLM_MODEL`, `LLM_TIMEOUT_S`) are read from environment, not hardcoded.
  - [ ] Errors raise `InferenceError` with a masked context. The raw prompt never appears in `__str__` or `__repr__`.
  - [ ] Streaming is exposed as an async iterator of `Chunk` (`text`, `done`, optional `confidence`).
- **Out-of-scope:** Embeddings, function-calling, tool use.
- **Open-questions:** _(none)_
- **Inference Impact:** yes
- **Data Sensitivity:** PHI
- **Gates Touched:** G4, G5, G7
- **Affected Layers:** infrastructure, usecases

## ASR Adapter

- **Goal:** Make the local-Whisper adapter a thin, replaceable component the rest of the backend talks to without knowing the wire format. Same shape as `#inference-adapter` for the LLM. As of 2026-05-12 the adapter exposes both a non-streaming `transcribe(...)` (BE-014/016) and a streaming `stream_transcribe(...)` (BE-017, gated by ADR-0003 + the frontend env-var flag).
- **Inputs:**
  - SPEC.md#asr-layer-contract
  - docs/adr/0001-voice-input-and-local-asr.md
  - docs/adr/0003-streaming-asr-chunked.md
  - .claude/rules/local-llm-and-phi.md
- **Acceptance:**
  - [ ] `app/infrastructure/asr/__init__.py` exports `LocalASRClient` (Protocol/ABC), `TranscribeParams`, `TranscribeResponse`, `TranscribeChunk`, `AudioPayload`, `ASRError`, and a `make_asr_client()` factory mirroring `make_llm_client()`.
  - [ ] `LocalASRClient` Protocol declares two coroutine methods: `transcribe(audio, params) -> TranscribeResponse` (non-streaming) and `stream_transcribe(audio, params) -> AsyncIterator[TranscribeChunk]` (streaming). Every implementation MUST provide both — the streaming method MAY internally call the non-streaming method per chunk.
  - [ ] `TranscribeChunk` (frozen dataclass): `text: str`, `chunk_index: int`, `chunk_count: int`, `done: bool`. When `done=True`, `text` holds the full assembled transcript across all chunks (mirrors the `Chunk(text=..., done=True)` completion-frame pattern from `#inference-adapter`).
  - [ ] `WhisperCppLocalASRClient` implements `LocalASRClient`; talks to `http://asr:8080` via whisper-server's `/inference` (or equivalent) endpoint over multipart form-data. The concrete class name MUST NOT be referenced from `usecases` — only the factory and the Protocol cross the boundary.
  - [ ] `WhisperCppLocalASRClient.stream_transcribe(...)` slices the post-transcode PCM WAV into `ASR_STREAM_CHUNK_SECONDS`-long segments using Python's standard `wave` module (no new heavy dep). Each segment is a complete WAV (44-byte header + N samples of PCM_S16LE @ 16 kHz mono). For each segment the implementation calls the same whisper-server `/inference` endpoint sequentially (no parallel dispatch — whisper.cpp serializes), then yields one `TranscribeChunk(text=segment_text, chunk_index=i, chunk_count=N, done=False)` per successful chunk. After the last chunk, the method yields a single `TranscribeChunk(text=assembled, chunk_index=N-1, chunk_count=N, done=True)`.
  - [ ] `FakeLocalASRClient.stream_transcribe(...)` is the default in unit tests; produces deterministic chunks (default: split the fixture transcript into 3 equal pieces) with a configurable `per_chunk_delay_s: float = 0.0` so latency-tier tests can drive `ASR_STREAM_FIRST_CHUNK_LATENCY_S` and the >10 s cancel tier deterministically. Supports `force_error_at_chunk: int | None`, `force_timeout: bool`, and `force_total_timeout: bool` for the error-path tests.
  - [ ] Configuration values `ASR_BASE_URL`, `ASR_MODEL`, `ASR_TIMEOUT_S`, `ASR_STREAM_CHUNK_SECONDS`, `ASR_STREAM_TOTAL_TIMEOUT_S`, `ASR_STREAM_FIRST_CHUNK_LATENCY_S` are read from environment, not hardcoded. Defaults: `ASR_MODEL=ggml-medium-q5_0.bin`, `ASR_TIMEOUT_S=90`, `ASR_STREAM_CHUNK_SECONDS=10`, `ASR_STREAM_TOTAL_TIMEOUT_S=180`, `ASR_STREAM_FIRST_CHUNK_LATENCY_S=25`. `ASR_STREAM_CHUNK_SECONDS` MUST be in the inclusive range [5, 20]; values outside the range MUST raise a configuration error at module import time (similar to current `ASR_TIMEOUT_S` parsing).
  - [ ] `transcribe(...)` accepts `AudioPayload` (bytes + content-type) and a `language: str = "ja"` parameter on `TranscribeParams`. `stream_transcribe(...)` accepts the same arguments. The implementation passes `language=ja` to whisper-server so vanilla Whisper does not fall back to English.
  - [ ] Errors raise `ASRError` with a masked context. The raw audio bytes, the filename, and the transcript MUST NOT appear in `__str__` or `__repr__`. Mirrors `InferenceError` from `app/infrastructure/llm/errors.py`. For `stream_transcribe`, mid-stream errors raise `ASRError` from within the async iterator at the failing chunk; chunks already yielded are preserved by the caller but the iterator stops.
  - [ ] Layer rule: `grep -RnE '^from app\.infrastructure\.asr' backend/app/{domain,usecases,interfaces}` returns hits only from `usecases/di.py`, `usecases/transcribe.py`, and `usecases/transcribe_stream.py` (the only consumers).
  - [ ] No persistence: both `transcribe(...)` and `stream_transcribe(...)` MUST receive `AudioPayload` as in-memory bytes (or a `SpooledTemporaryFile` reference) and MUST NOT write the audio (or any chunked slice) to a named file on disk. The chunk-segmentation step uses `io.BytesIO` + `wave.open(..., "wb")` to build each segment's WAV in memory.
- **Out-of-scope:** Parallel chunk processing, chunk overlap (v1 uses 0 s overlap), diarization, language detection, transcript translation, batch processing, kotoba-whisper variant swap.
- **Open-questions:** _(none — ADR-0001 + ADR-0003 close them)_
- **Inference Impact:** yes
- **Data Sensitivity:** PHI
- **Gates Touched:** G4, G5, G7
- **Affected Layers:** infrastructure, usecases

## Persistence

- **Goal:** Define the storage shape for patient/encounter/record data so PHI columns are explicit and masking-on-log is enforceable.
- **Inputs:**
  - SPEC.md#domain-glossary
- **Acceptance:**
  - [ ] Tables: `patient`, `encounter`, `record_draft`, `record_final`, `audit_log`.
  - [ ] PHI columns flagged via a `phi=True` SQLAlchemy column-info marker; the logging filter masks any value carrying it.
  - [ ] `record_final` rows are immutable (no UPDATE allowed; corrections are new rows referencing predecessors).
  - [ ] All persistence goes through repositories in `app/infrastructure/db/`. No raw SQL in `usecases` or `interfaces`.
  - [ ] Migrations live under `backend/migrations/` with Alembic. Each migration is reviewed against PHI implications.
- **Out-of-scope:** Read replicas, sharding, OLAP exports.
- **Open-questions:** _(none)_
- **Data Sensitivity:** PHI
- **Gates Touched:** G4, G7
- **Affected Layers:** infrastructure, usecases

## API Surface

- **Goal:** Anchor the public HTTP shape so the frontend can be implemented in parallel.
- **Inputs:**
  - frontend/SPEC.md#frontend-mission
- **Acceptance:**
  - [ ] All endpoints declared with FastAPI `response_model=`; no untyped responses.
  - [ ] Errors normalised to `{ "code": str, "message": str }`; messages never include PHI.
  - [ ] `/health` returns 200 when Postgres and llm are both reachable; 503 otherwise.
  - [ ] OpenAPI schema is generated at `/openapi.json`; the FastAPI interactive `/docs` (Swagger UI) and `/redoc` sites are NOT mounted (`docs_url=None`, `redoc_url=None`). Rationale: this project is a local-only PoC per `CLAUDE.md` §2 Scope — there is no dev/prod build split, and the interactive docs UI is not user-facing.
- **Out-of-scope:** GraphQL, WebSocket transport (if needed, file an ADR).
- **Open-questions:** _(none)_
- **Gates Touched:** G1, G2, G6, G7
- **Affected Layers:** interfaces

## Transcribe Endpoint

- **Goal:** Expose `POST /encounters/{encounter_id}/transcribe` that accepts a single short audio clip from the frontend, routes it through `LocalASRClient`, and returns the Japanese transcript. The endpoint is stateless — no DB write, no audio retention. It is a thin HTTP wrapper over the ASR adapter.
- **Inputs:**
  - SPEC.md#asr-layer-contract — wire contract for `LocalASRClient`
  - backend/SPEC.md#asr-adapter — adapter shape and error type
  - backend/SPEC.md#api-surface — error envelope, response_model rule
  - backend/SPEC.md#authentication — `get_current_clinician` dependency required because audio is PHI
  - docs/adr/0001-voice-input-and-local-asr.md
- **Acceptance:**
  - [ ] Endpoint `POST /encounters/{encounter_id}/transcribe` declared in `app/interfaces/routers/transcribe.py` (new router file) with `response_model=TranscribeRead`.
  - [ ] Request body: `multipart/form-data` with one file field `audio` (WebM/Opus container; backend rejects other content-types with 415).
  - [ ] Server-side limits enforced before the ASR call: payload ≤2 MB, content-type ∈ `{audio/webm, audio/webm;codecs=opus}`, encounter exists (404 `encounter_not_found`).
  - [ ] On success returns 200 `{ "text": str, "encounter_id": UUID, "duration_seconds": float | None }`. `duration_seconds` is whatever the ASR backend reports; null if not available.
  - [ ] On `ASRError` returns 503 with `{ "code": "transcription_unavailable", "message": "音声の文字起こしに失敗しました。" }`. Mirrors the BE-006 `inference_unavailable` mapping for `InferenceError`.
  - [ ] On timeout returns 504 `{ "code": "transcription_timeout", "message": "音声の文字起こしがタイムアウトしました。" }`.
  - [ ] Endpoint requires `clinician_id: UUID = Depends(get_current_clinician)`; missing/malformed header returns 401 per `#authentication`.
  - [ ] PHI: audio bytes are never written to logs. Filename, if present in the multipart part, is dropped at the router boundary (never logged, never stored). The transcript is logged only via `mask_phi(text)` at DEBUG level; INFO logs use `len(text)` and `short_id(encounter_id)` only.
  - [ ] No DB write. No `audit_log` row is written for transcription (out of scope for v1 — voice input is a UI affordance; the audit trail of clinical content lives on the resulting `record_draft`).
  - [ ] Layer rule: `grep -RnE '^from app\.infrastructure' backend/app/interfaces/routers/transcribe.py` → 0 hits.
  - [ ] Usecase: `app/usecases/transcribe.py` exports `transcribe_audio(encounter_id, clinician_id, audio, asr_client, encounter_repo)`; verifies encounter exists; calls `asr_client.transcribe(...)`; returns the transcript. `ASRError` propagates as-is.
- **Out-of-scope:** Persistence of audio or transcripts (frontend appends to `clinical_input` and discards on submit). Audit-log row for transcribe (audit happens on the resulting draft). Streaming transcription (delivered in `#transcribe-streaming-endpoint` — additive, this Block's contract is preserved unchanged). Speaker diarization. Audio editing / trimming on the backend.
- **Open-questions:** _(none — ADR-0001 closes them)_
- **Inference Impact:** yes; ASR path; `whisper.cpp medium-q5_0`; `ASR_TIMEOUT_S=90`; co-resident with `gemma4:e4b`.
- **Data Sensitivity:** PHI; audio bytes and transcript are PHI per ADR-0001; never echoed in logs at INFO level; never persisted past the request lifetime.
- **Gates Touched:** G1, G2, G3, G4, G5, G6, G7
- **Affected Layers:** usecases (new `transcribe.py`), interfaces (new router `transcribe.py`), infrastructure (consumed via `LocalASRClient` per `#asr-adapter`)

## Transcribe Streaming Endpoint

- **Goal:** Expose `POST /encounters/{encounter_id}/transcribe/stream` — a Server-Sent Events (SSE) sibling of `#transcribe-endpoint`. The endpoint accepts the same `multipart/form-data` audio payload but streams progressive transcript chunks back as SSE frames, using the exact frame envelope established by BE-013 (streaming draft). The non-streaming endpoint remains unchanged for rollback; both endpoints share the same usecase boundary, the same `LocalASRClient`, and the same `_transcode_to_wav` step from BE-016. The streaming variant lets the clinician see progress before the full 60 s clip is processed.
- **Inputs:**
  - SPEC.md#asr-layer-contract — wire contract for streaming variant; rollback expectation
  - backend/SPEC.md#asr-adapter — `LocalASRClient.stream_transcribe`, `TranscribeChunk` shape, env vars
  - backend/SPEC.md#transcribe-endpoint — non-streaming endpoint preserved unchanged; size/content-type validation reused
  - backend/SPEC.md#api-surface — error envelope, response_model rule
  - backend/SPEC.md#authentication — `get_current_clinician` dependency required because audio is PHI
  - backend/app/interfaces/routers/drafts.py — BE-013 SSE envelope pattern (`data: {...}\n\n`, `event: complete`, `event: error`) — the streaming transcribe endpoint MUST emit the same envelope shape so the frontend SSE parser code is reusable mechanically
  - docs/adr/0003-streaming-asr-chunked.md
- **Acceptance:**
  - [ ] Endpoint `POST /encounters/{encounter_id}/transcribe/stream` declared in `app/interfaces/routers/transcribe.py` (extend existing router file, do not create a second router) with `response_class=StreamingResponse`, `status_code=200`, `media_type="text/event-stream"`.
  - [ ] Request body: identical to `#transcribe-endpoint` — `multipart/form-data` with one file field `audio` (WebM/Opus container; backend rejects other content-types with 415).
  - [ ] Server-side limits enforced before opening the SSE stream: payload ≤2 MB, content-type ∈ `{audio/webm, audio/webm;codecs=opus}`, encounter exists (404 `encounter_not_found`). These checks happen synchronously and return a standard HTTP error response (NOT an SSE error frame). The stream MUST NOT open until all preconditions pass.
  - [ ] SSE frame format (binding — mirrors BE-013 exactly so the frontend parser reuses the BE-013 frame structure):
    - Chunk frame: `data: {"text": "<chunk_text>", "chunk_index": <int>, "chunk_count": <int>, "done": false}\n\n`
    - Completion frame: `event: complete\ndata: {"full_text": "<assembled>", "duration_seconds": <float|null>, "chunk_count": <int>}\n\n`
    - Mid-stream error frame: `event: error\ndata: {"code": "transcription_unavailable" | "transcription_timeout", "chunk_index": <int>}\n\n`. After an error frame the stream closes; no further chunks follow.
  - [ ] On `ASRError(timeout=True)` mid-stream the error code is `transcription_timeout`; on any other `ASRError` mid-stream the error code is `transcription_unavailable`. The router MUST NOT include `exc.masked_context` or any audio metadata in the SSE error frame payload — only the code + chunk_index.
  - [ ] Endpoint requires `clinician_id: UUID = Depends(get_current_clinician)`; missing/malformed header returns 401 per `#authentication` (synchronous, before stream opens).
  - [ ] PHI: audio bytes never written to logs. Filename, if present in the multipart part, is dropped at the router boundary. Each chunk's text MAY be logged only at DEBUG level via `mask_phi(text)`; INFO logs use `len(text)` and `short_id(encounter_id)` only — same discipline as `#transcribe-endpoint`. Chunk indices (small integers) are NOT PHI and MAY appear in INFO logs.
  - [ ] No DB write. No `audit_log` row for transcription (out of scope for v1 — same as `#transcribe-endpoint`).
  - [ ] Layer rule: `grep -RnE '^from app\.infrastructure' backend/app/interfaces/routers/transcribe.py` → 0 hits (existing rule from `#transcribe-endpoint` extends to the new endpoint).
  - [ ] Usecase: `app/usecases/transcribe_stream.py` exports `stream_transcribe_audio(*, audio, params, encounter_id, clinician_id, asr, encounter_repo) -> AsyncGenerator[TranscribeChunk, None]`. The usecase: (1) verifies the encounter exists (raises `EncounterNotFound` synchronously — before any LLM/ASR work, so the router maps it to 404 before opening the SSE stream); (2) calls `asr.stream_transcribe(audio, params)`; (3) yields each `TranscribeChunk` to the caller; (4) preserves `ASRError` propagation semantics (errors fall out of the iterator at the failing chunk). No DB writes. No audit log. UUID logged via `short_id(...)` at INFO; transcript text only at DEBUG via `mask_phi(...)`.
  - [ ] Total-timeout guard: the usecase wraps the iteration in `asyncio.wait_for(..., timeout=ASR_STREAM_TOTAL_TIMEOUT_S)` per chunk-yield boundary. On total-timeout, raise `ASRError("stream total timeout", timeout=True)` which the router converts to an SSE `event: error` frame with code `transcription_timeout`. Per-chunk timeouts continue to be enforced by `WhisperCppLocalASRClient` via the existing `ASR_TIMEOUT_S=90` httpx timeout per `/inference` call.
  - [ ] Cancellation: when the HTTP connection drops (client AbortController), the SSE generator's outer `try/finally` MUST release the in-flight subprocess (transcode) and any pending httpx call. Use FastAPI's standard `StreamingResponse` close hook — no custom cancellation channel.
  - [ ] DI: `make_stream_transcribe_audio(...)` factory in `app/usecases/di.py`. Type alias `StreamTranscribeAudioCallable = Callable[[AudioPayload, TranscribeParams | None, UUID, UUID], AsyncGenerator[TranscribeChunk, None]]`. Mirrors `make_stream_record_draft` (BE-013).
  - [ ] Non-streaming endpoint preserved unchanged. The router file gains a new endpoint definition; existing `post_transcribe` and its tests MUST continue to pass without modification.
  - [ ] Tests: `tests/usecases/test_transcribe_stream.py` covers (a) happy path: 3-chunk fake stream yields 3 data frames + 1 complete frame in order; (b) encounter not found → `EncounterNotFound` raised before any ASR call; (c) `ASRError` at chunk N → iterator stops at chunk N (no further yields); (d) total-timeout → `ASRError(timeout=True)` is raised at the wait_for boundary. `tests/interfaces/test_transcribe_router.py` is extended with: (e) 200 SSE happy path asserting raw SSE bytes match the contract; (f) 401/404/415/422 synchronous before-stream errors; (g) mid-stream `transcription_unavailable` error frame; (h) mid-stream `transcription_timeout` error frame.
- **Out-of-scope:**
  - Parallel chunk processing (whisper.cpp serializes).
  - Real-time microphone → backend continuous streaming (different audio-capture paradigm; would need WebSocket / MediaRecorder timeslice).
  - Chunk overlap (v1 uses 0 s).
  - Audio persistence, audit log, transcript persistence.
  - Multi-clip queueing.
  - Resumable streams (mid-stream reconnect with offset).
  - Replacing `#transcribe-endpoint` — the non-streaming endpoint stays as the rollback path.
- **Open-questions:** _(none — ADR-0003 closes them)_
- **Inference Impact:** yes; ASR streaming path; `whisper.cpp medium-q5_0`; `ASR_TIMEOUT_S=90` per chunk; `ASR_STREAM_TOTAL_TIMEOUT_S=180` for the whole stream; first-chunk p95 ≤25 s; co-resident with `gemma4:e4b`. Memory footprint unchanged from BE-014 — sequential chunk calls reuse the loaded whisper.cpp model.
- **Data Sensitivity:** PHI; audio bytes, chunk-text, and assembled transcript are PHI per ADR-0001. Never echoed in INFO logs, never in SSE error frame payloads, never persisted past the request lifetime. Chunked PCM byte slices are PHI on the same footing as the parent audio and MUST NOT be written to disk.
- **Gates Touched:** G1, G2, G3, G4, G5, G6, G7
- **Affected Layers:** usecases (new `transcribe_stream.py` + extend `di.py`), interfaces (extend `transcribe.py` router), infrastructure (extend `LocalASRClient` Protocol + `WhisperCppLocalASRClient` + `FakeLocalASRClient` per `#asr-adapter`)

## Authentication

- **Goal:** Implement the PoC clinician-identification scheme defined in `SPEC.md#authentication-poc` as a FastAPI dependency, and migrate every existing `clinician_id`-in-body and `_PLACEHOLDER_CLINICIAN_ID` usage off those affordances. The header is the single source of truth for the active clinician identifier inside the backend.
- **Inputs:**
  - SPEC.md#authentication-poc — the project-level Block this section refines
  - .claude/rules/local-llm-and-phi.md §4 — operational-read authorisation requirement
  - backend/SPEC.md#api-surface — error envelope
  - backend/SPEC.md#layer-boundaries — dependency lives in `interfaces`; usecases consume the resolved UUID
- **Acceptance:**
  - [ ] A new module `app/interfaces/auth.py` exports a FastAPI dependency with the shape `get_current_clinician(x_clinician_id: UUID | None = Header(default=None, alias="X-Clinician-Id")) -> UUID`. The dependency MUST raise `HTTPException(status_code=401, detail={"code": "unauthenticated", "message": "Clinician identification required."})` when the header is absent, empty, or fails UUID parsing.
  - [ ] Every PHI-returning router endpoint declares `clinician_id: UUID = Depends(get_current_clinician)`. PHI-returning endpoints include: all POST/PATCH/GET endpoints in `app/interfaces/routers/{patients,encounters,drafts,finals}.py`. Non-PHI endpoints (`/health`, `/ping`, `/openapi.json`) MUST NOT add the dependency.
  - [ ] Request-body Pydantic models lose their `clinician_id` field: `EncounterCreate`, `DraftEdit`, `FinalizeRequest`, `FinalCorrectRequest`. The existing `model_config = ConfigDict(extra="forbid")` on each will reject the old field as an unknown property (422).
  - [ ] The placeholder constant `_PLACEHOLDER_CLINICIAN_ID` is removed from every usecase module (`app/usecases/patient.py`, `app/usecases/draft.py`, `app/usecases/final.py`, and any other site). Every usecase that writes `audit_log.actor` MUST receive `clinician_id` from the router (which got it from the dependency); no usecase fabricates an actor.
  - [ ] Tests use a fixed test clinician UUID supplied via the `X-Clinician-Id` header in TestClient calls. A shared `pytest` fixture in `tests/conftest.py` exposes the value and the helper for header construction. Tests asserting 401 behaviour pass requests without the header (or with a non-UUID value) and assert the envelope `{ "code": "unauthenticated", "message": "Clinician identification required." }`.
  - [ ] Layer rule: `app/interfaces/auth.py` MUST NOT import from `app/usecases/` or `app/infrastructure/`. Routers import `get_current_clinician` from `app.interfaces.auth`.
  - [ ] Logging: the resolved clinician UUID is logged through `short_id(...)` at INFO level (consistent with BE-011). The raw header value MUST NOT appear in any `logger.*` call at INFO or higher.
- **Out-of-scope:**
  - Authentication provider integration (SSO, JWT issuer, OAuth2, OIDC, SAML).
  - Password storage, password reset, MFA, WebAuthn, credential vaulting.
  - Role-based authorisation beyond clinician identity (e.g. admin/auditor/superuser splits, scope claims).
  - Session management, refresh tokens, logout, token revocation.
  - CSRF protection, rate limiting per clinician, account lockout.
  - mTLS or transport-level identity binding.
  - Header-signing, HMAC verification of the header value, or any form of cryptographic trust on `X-Clinician-Id`.
  - Frontend identity-source design (login screen, clinician picker, "remember me") — the frontend chooses how to obtain the UUID for the PoC; the backend only consumes it.
- **Open-questions:** _(none — header-trust PoC is intentional)_
- **Inference Impact:** no
- **Data Sensitivity:** PHI; the clinician UUID is logged via `short_id(...)` only; the raw header value MUST NOT leak into error envelopes, stack traces, or INFO logs.
- **Gates Touched:** G1, G2, G3, G4, G6, G7
- **Affected Layers:** interfaces (new `auth.py`, router signature changes, request-model field removals), usecases (placeholder removal; existing `clinician_id` parameters are preserved at the usecase boundary)

## Default Gates

Every backend feature task sets at minimum: `Gates Touched: G1, G2, G3, G6, G7`. Add G4 for any task that touches PHI columns, prompts, or logging. Add G5 for any task that exercises the inference path. Add G0 when `docker-compose.yml`, base image, or migrations are touched.

## Recap of cross-cutting rules (binding)

- Pydantic at every interface boundary; no untyped dicts cross layers.
- No `# type: ignore` without an inline reason and a follow-up note in `NOTES.md`.
- Logging uses the project logger; never `print` in committed code.
- Tests: unit tests use `FakeLocalLLMClient` and a transactional Postgres fixture. Integration tests against the real `llm` container live behind a `pytest -m integration` marker.
