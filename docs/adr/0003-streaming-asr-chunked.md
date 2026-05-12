# ADR 0003: Chunked streaming ASR with env-var rollback

- **Status:** Accepted
- **Date:** 2026-05-12
- **Owner:** Planner (Claude Opus 4.7)
- **Related Spec:** `SPEC.md#asr-layer-contract`, `backend/SPEC.md#asr-adapter`, `backend/SPEC.md#transcribe-streaming-endpoint`, `frontend/SPEC.md#voice-capture`, `frontend/SPEC.md#voice-input-latency-ux`

## Context

Voice input shipped in BE-014/BE-016/FE-009 and works end-to-end. Real-world testing on 2026-05-12 shows the latency feels long: whisper.cpp processes the entire 60 s clip as one blocking inference, ~30–90 s wall-clock on CPU before any feedback reaches the clinician. ADR-0001 §Alternatives explicitly rejected streaming partial transcripts "for v1" and tracked it as "revisit after first-cut ships". The first cut shipped; the revisit gate is met.

Three forcing functions surface together:

1. **Perceived-latency cliff.** The non-streaming UI spinner stays static for 30–90 s after the user stops recording. The 5-tier `#voice-input-latency-ux` (FE-009) already escalates to a Cancel button at >10 s, but the user has no signal that the system is making progress; many will assume it has hung and re-record. A 60 s spinner with no progressive feedback is the kind of UX cliff that pushes clinicians back to typing — defeating the feature.
2. **whisper.cpp serializes inference.** We cannot meaningfully parallelize chunks server-side. Streaming has to be chunked-sequential: split the WAV PCM into N second-aligned slices, call `/inference` for each in order, emit each transcript fragment as it lands. The architectural shape is dictated by whisper.cpp's behaviour, not by us.
3. **Reversibility is required.** Streaming introduces three new failure modes — boundary corruption between chunks, mid-stream error handling, partial-transcript discipline — that we cannot fully test against the user's real recordings until the user uses it. The user explicitly asked for a rollback path. A flag that flips the behaviour back to BE-016 with no code change is the only honest way to ship this without burning the existing working path.

Without an ADR, the change would touch the ASR Adapter contract, the API surface, the frontend molecule's state machine, and a new env-var-flag pattern that has no precedent in this project — a coordination problem big enough to warrant a single binding decision.

## Decision

We will add a streaming variant of the ASR transcribe endpoint as an **additive** capability, gated by the frontend env var `NEXT_PUBLIC_ASR_STREAMING_ENABLED` (default `"false"`), and we will preserve the existing non-streaming endpoint and frontend code path unchanged so that flipping the flag to `"false"` restores BE-016 behaviour at the next page load without any code modification.

Concretely:

- **Backend topology:** The `LocalASRClient` Protocol gains a second method `stream_transcribe(audio, params) -> AsyncIterator[TranscribeChunk]` alongside the existing `transcribe(audio, params) -> TranscribeResponse`. Every implementation (`WhisperCppLocalASRClient`, `FakeLocalASRClient`) provides both. The streaming implementation: (a) reuses the existing `_transcode_to_wav` step from BE-016 to produce a 16 kHz mono 16-bit PCM WAV in memory; (b) slices the PCM payload of that WAV into `ASR_STREAM_CHUNK_SECONDS`-long segments (default 10 s, configurable in the inclusive range [5, 20]); (c) rebuilds a complete WAV (44-byte header + slice) per segment using only Python's standard `wave` module — no new heavy dependency; (d) POSTs each segment to whisper-server `/inference` sequentially; (e) yields one `TranscribeChunk(text=..., chunk_index=i, chunk_count=N, done=False)` per successful chunk, then a final `TranscribeChunk(text=assembled, chunk_index=N-1, chunk_count=N, done=True)`. A new endpoint `POST /encounters/{encounter_id}/transcribe/stream` exposes this via SSE using the exact same frame envelope as BE-013 (streaming draft): `data: {...}\n\n` for chunks, `event: complete\ndata: {...}\n\n` for completion, `event: error\ndata: {...}\n\n` for mid-stream failures. The existing `POST /encounters/{encounter_id}/transcribe` endpoint stays unchanged.

- **Timeouts:** Per-chunk timeout reuses `ASR_TIMEOUT_S=90` (existing). End-to-end streaming timeout is a new env var `ASR_STREAM_TOTAL_TIMEOUT_S=180` enforced by the usecase via `asyncio.wait_for` at the chunk-yield boundary. First-chunk latency target `ASR_STREAM_FIRST_CHUNK_LATENCY_S=25` is a UX threshold, not a hard timeout.

- **Frontend dispatch fork:** A new constant `ASR_STREAMING_ENABLED = process.env.NEXT_PUBLIC_ASR_STREAMING_ENABLED === "true"` in `src/lib/constants.ts` (default `false`). The `useVoiceCapture` hook reads this constant once at module scope and dispatches to either `transcribeAudio` (existing) or a new `streamTranscribeAudio` (FE-013). When the flag is `false`, FE-009 behaviour is preserved bit-for-bit — no new code path runs, no new test changes existing test green status.

- **Progressive feedback discipline:** The streaming UI shows accumulated partial transcripts inside the `VoiceCapture` molecule's existing aria-live region (chunk-index counter announced) plus a non-aria-live `<pre>` block (visual partial-text only — avoids loud screen-reader re-announcements of PHI). The parent textarea is NOT touched during streaming. Only on `event: complete` does the full transcript atomically append to the textarea via the existing `onTranscript(fullText)` callback. Mid-stream cancel or error discards all chunks; no partial transcript ever lands in the editable area.

- **Rollback contract:** If streaming quality degrades in the field (boundary corruption, accuracy regression, latency regression), the operator sets `NEXT_PUBLIC_ASR_STREAMING_ENABLED=false` in `docker-compose.yml`, rebuilds the frontend image, and behaviour reverts to BE-016 instantly. The backend keeps both endpoints so an in-progress hot fix can be even narrower (no rebuild required if a server-side issue is patched). The streaming endpoint is never the only path to transcription; it is always the opt-in extension.

This is a single decision because the five parts (Protocol extension, new endpoint, env-var flag, frontend dispatch fork, rollback design) cannot land independently without leaving the project in a broken state.

## Consequences

- **Positive:**
  - Clinicians see chunk-by-chunk progress within ~15–25 s instead of waiting 30–90 s for the full clip — perceived latency drops dramatically.
  - The rollback path is mechanical and instant: one env-var flip restores known-good behaviour without re-implementing anything.
  - The streaming endpoint reuses the BE-013 SSE envelope structure, so the frontend's SSE parser is identical in shape — minimizing the surface area of new code that can break.
  - The Protocol-level addition (`stream_transcribe` method) is straightforward to mock in tests via `FakeLocalASRClient`, keeping G3 unit-test discipline intact.
  - Total wall-clock latency is only marginally worse than non-streaming (sequential chunk overhead ~1–2 s per chunk for 6 chunks at 10 s each, well within `ASR_STREAM_TOTAL_TIMEOUT_S=180`).

- **Negative:**
  - Per-chunk inference startup cost is paid 6 times instead of once for a 60 s clip — total wall-clock is slightly worse than the single-blob path. Accepted because perceived latency is the user-visible metric and improves.
  - Word-boundary corruption is real at chunk boundaries when overlap is 0. We accept this in v1 because (a) clinicians edit the transcript in place before generating the draft, so a few misread words at boundaries are normal-friction not blocking; (b) overlap is a v2 enhancement to revisit after first user feedback on streaming.
  - The compose surface grows by three env vars (`ASR_STREAM_CHUNK_SECONDS`, `ASR_STREAM_TOTAL_TIMEOUT_S`, `ASR_STREAM_FIRST_CHUNK_LATENCY_S`) and one frontend env var (`NEXT_PUBLIC_ASR_STREAMING_ENABLED`). G0 (Compose-up) is unaffected.
  - The frontend ships two transcription code paths gated by an env var; tests have to cover both branches. Acceptable because the gating is at module scope (a single constant read) and the branch surface is small.
  - First-chunk feedback is still ~15–25 s, not sub-second. Real-time streaming (true continuous mic-to-server) is a different paradigm and is explicitly out-of-scope.

- **Reversibility:** Cheap. Set `NEXT_PUBLIC_ASR_STREAMING_ENABLED=false` and rebuild the frontend image; the non-streaming endpoint and code path remain fully functional. The streaming endpoint can be left in place (dormant) or, if necessary, removed in a follow-up Block — no other code depends on it.

## Alternatives considered

- **No streaming, accept the 30–90 s blocking spinner:** rejected — real-world testing shows clinicians will assume the system hung and abandon the feature. The whole point of voice input is to be faster than typing; a 60 s spinner inverts that promise.
- **MediaRecorder timeslice → continuous mic-to-server WebSocket multiplexing:** rejected for v1 — different audio-capture paradigm, requires a WebSocket server, a new multipart-streaming protocol on the backend, and a much larger frontend rewrite. The feature value (progressive feedback) is delivered by chunked-sequential at far less risk.
- **Parallel chunk dispatch (`asyncio.gather` across chunks):** rejected — whisper.cpp serializes inference in the underlying ASR container, so concurrent calls queue server-side anyway. Parallelism adds complexity (out-of-order chunk reassembly, partial-failure handling) for zero throughput gain.
- **Chunk overlap (1–2 s):** deferred to v2 — non-zero overlap is the natural fix for word-boundary corruption, but it adds per-chunk dedup logic and an arbitrary trim parameter. Ship v1 with 0 overlap, measure boundary corruption on real recordings, then revisit with data. Tracked as an Open follow-up below.
- **Replace `transcribe` with `stream_transcribe` and delete the old endpoint:** rejected — violates the user's explicit ask for a rollback path. The user's rationale is sound: streaming has more failure modes and we cannot fully de-risk them in unit tests.
- **Use a hosted streaming-ASR SDK (Deepgram WebSocket, AssemblyAI realtime):** forbidden by `.claude/rules/local-llm-and-phi.md` §1 (no hosted-ASR SDKs). The same network-egress rule that forbids hosted LLMs forbids hosted ASR. The local-only constraint is binding.
- **Switch the ASR variant to a faster model (`kotoba-whisper-v2.0-ggml`):** orthogonal — even with a faster model, a 60 s clip on CPU still takes meaningful seconds, and the perceived-latency problem remains. Variant swap is tracked separately by ADR-0001's Open follow-ups; this ADR does not preempt that decision.
- **Increase `ASR_TIMEOUT_S` and accept the blocking spinner with a clearer JP message:** rejected — the user already has the 60-second-record-cap UX. Lengthening the timeout makes the cliff worse, not better.

## Gates affected

- **G0 (Compose-up):** unchanged. Three new backend env vars and one new frontend env var added with defaults; G0 healthcheck threshold remains ≤120 s.
- **G4 (Security / PHI):** unchanged in shape. Streaming SSE frames carry transcript text — the same PHI class as the non-streaming response body. The new `security-check` grep matrix has nothing new to look for (the existing `getUserMedia|MediaRecorder` and `http://asr` rules still cover the surface). The chunked PCM byte slices are PHI on the same footing as the parent audio and MUST NOT touch disk — explicit in the SPEC.
- **G5 (Cost / Inference budget):** new thresholds — first-chunk p95 ≤25 s, total streaming p95 ≤180 s. Co-resident memory budget unchanged (sequential chunk calls reuse the loaded whisper.cpp model — no second model load).
- **G7 (Architecture):** the `LocalASRClient` Protocol extension is additive; the existing layer-rule `grep -RnE '^from app\.infrastructure\.asr' backend/app/{domain,usecases,interfaces}` is extended to include `usecases/transcribe_stream.py` as an allowed consumer. The frontend `streamTranscribeAudio` uses raw `fetch` (apiFetch does not support multipart + SSE) — same precedent as `streamRecordDraft` (FE-008).

## Open follow-ups

- [ ] Generator implements `BE-017` (streaming endpoint + Protocol extension + `_slice_wav` helper + usecase + DI factory + tests) per the Block handoff that references this ADR.
- [ ] Generator implements `FE-013` (streaming service + hook extension + molecule extension + env-var constant + tests) per the Block handoff that references this ADR. BE-017 ships first; FE-013 ships against the live streaming endpoint.
- [ ] cost-check is invoked once the streaming path is live in the dev environment to verify first-chunk p95 ≤25 s and total p95 ≤180 s for a real 60 s recording on the reference CPU.
- [ ] After streaming has been used for ≥1 week of real recordings, evaluate word-boundary corruption rate. If it is meaningful, file a follow-up ADR to introduce non-zero chunk overlap (1–2 s) with the trim parameter.
- [ ] If first-chunk p95 exceeds 25 s in cost-check, revisit `ASR_STREAM_CHUNK_SECONDS` default downward (10 → 7 or 5) — smaller chunks trade total wall-clock for faster first feedback.
- [ ] If the streaming path becomes the dominant code path with no regressions for ≥1 month, file a superseding ADR to flip `NEXT_PUBLIC_ASR_STREAMING_ENABLED` default to `"true"`. Removing the non-streaming endpoint entirely is a separate, later ADR — the operational rollback path stays valuable indefinitely.
