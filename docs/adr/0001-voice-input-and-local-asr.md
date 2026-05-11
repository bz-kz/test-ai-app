# ADR 0001: Voice input and local ASR service

- **Status:** Accepted
- **Date:** 2026-05-12
- **Owner:** Planner (Claude Opus 4.7)
- **Related Spec:** `SPEC.md#asr-layer-contract`, `backend/SPEC.md#asr-adapter`, `frontend/SPEC.md#voice-capture`

## Context

Clinicians want to dictate the subjective/objective narrative on `/encounters/[encounterId]/draft` instead of typing the full clinical input. The repo today has no audio capture, no ASR service, and no rule clause that treats spoken patient narrative as PHI. Three forcing functions surface together:

1. `.claude/rules/local-llm-and-phi.md` §3 enumerates PHI textually but never says "audio". Web Speech API and any browser-direct hosted ASR (Deepgram, AssemblyAI, Azure Speech) would ship the patient narrative off-network, which is the same egress class that §1 forbids for LLM traffic. The rule needs to extend to audio explicitly so future agents cannot point at "audio is not in the §3 list" as a loophole.
2. The compose topology has only `frontend / backend / postgres / llm`. Adding speech-to-text requires either a new internal-only service or co-locating ASR inside `backend` (which the DDD layer split forbids — see `backend/SPEC.md#layer-boundaries`).
3. `SPEC.md#hardware-assumptions` was just (INF-003) raised to require Docker Desktop ≥12 GB because `gemma4:e4b` alone needs ~10 GiB resident. Adding a second model has to either fit in the existing headroom or push the Docker-memory floor up. The reference-hardware RAM (24 GB) has room; Docker Desktop slider does not without an explicit revision.

Without an ADR, the change would touch `.claude/rules/local-llm-and-phi.md` (human-only per `AGENTS.md` §3), the Hardware Assumptions Block, and three sub-specs at once — a coordination problem big enough to warrant a single binding decision record.

## Decision

We will add voice input as a feature by **adding a new internal-only `asr` Docker Compose service running whisper.cpp's `whisper-server` HTTP image (Apache-2.0) with the `medium-q5_0` GGML model, gated by the same `localhost`-only network boundary as `llm`, and we will extend `.claude/rules/local-llm-and-phi.md` §3 to declare audio/voice as PHI.**

Concretely:

- **ASR runtime variant:** `whisper.cpp` `medium-q5_0` GGML model (Japanese accuracy >90% at <2s on a 4-core CPU per upstream benchmarks; ~0.7–0.9 GiB resident at Q5_0 quantization). The model file is downloaded into the `asr_data` volume on first boot, mirroring how `gemma4:e4b` is pulled into `ollama_data`. The variant is read from a single environment variable `ASR_MODEL` so a swap to `kotoba-whisper-v2.0-ggml` (~1.5 GiB, distilled-for-Japanese) is a config change rather than a code change. Switching variants requires a follow-up ADR — the same discipline `SPEC.md#inference-layer-contract` already imposes on `LLM_MODEL`.
- **Network boundary:** the `asr` service joins the existing internal compose network, publishes no host ports, and exposes only `http://asr:<port>` (whisper-server default is 8080; the project pins `ASR_BASE_URL=http://asr:8080`). The browser MUST NOT call ASR directly — audio is sent from frontend to `backend`, and only `backend` calls `asr`. This mirrors the LLM rule from `.claude/rules/local-llm-and-phi.md` §1.
- **PHI rule extension:** clause §3 of `.claude/rules/local-llm-and-phi.md` is extended so that "PHI" enumerates audio/voice recordings of patient narrative. Audio bytes are forbidden from logs, from disk persistence past the request lifetime, from browser storage, and from any non-`asr` egress. Transcripts inherit the same masking expectation as `clinical_input` and `draft.content`.
- **Hardware Assumptions revision:** the reference Docker Desktop memory allocation is raised from "≥12 GB" to "≥13 GB" (10 GiB gemma4:e4b + ~1 GiB whisper.cpp medium-q5 + ~2 GiB headroom for backend/postgres/frontend/Docker overhead). 16 GB remains the recommendation for users who want headroom to swap in the kotoba-whisper variant or to retain comfortable margin.

This is a single decision because the four parts (rule extension, service addition, model pick, memory floor) cannot land independently without leaving the project in a broken state.

## Consequences

- **Positive:**
  - Clinicians get voice input on the draft page without any audio leaving the local Docker network.
  - The PHI rule now mechanically forbids the most likely future regression (someone reaching for Web Speech API or a hosted-ASR SDK).
  - The `LocalASRClient` interface mirrors `LocalLLMClient`, so the same testing pattern (`FakeLocalASRClient` as default in unit tests) is available out of the gate.
  - whisper.cpp medium-q5 fits inside the existing reference RAM (24 GB) without forcing users to upgrade hardware; the Docker memory slider bump (12 → 13 GiB) is the only operational ask.
- **Negative:**
  - The compose footprint grows from four services to five. G0 (Compose-up) gains a new healthcheck target.
  - First-boot weight pull adds ~0.7 GiB of bandwidth (model file) and ~30 s of wall-clock setup time the first time a developer runs `docker compose up -d`.
  - Japanese WER on whisper.cpp medium-q5 is meaningfully worse than kotoba-whisper-v2.0; clinicians WILL edit the transcript before it becomes useful input. We accept this because the transcript is editable in-place inside the existing `clinical_input` textarea — the clinician is the editor of last resort per `SPEC.md#product-goal`.
  - Browser microphone permission is a new UX surface; some users will deny it, and the page must degrade to text-only without breaking the existing typing flow.
- **Reversibility:** Moderate. Removing `asr` is a one-service compose edit plus deleting `app/infrastructure/asr/` and the `VoiceCapture` molecule; nothing else depends on its data shape. Reverting the rule clause requires a superseding ADR.

## Alternatives considered

- **Web Speech API in-browser:** rejected — sends audio to vendor servers (Google by default in Chrome), which violates `.claude/rules/local-llm-and-phi.md` §1 by the same egress reasoning that already forbids hosted LLM SDKs. Not a viable PoC option even with a user-consent banner.
- **kotoba-whisper-v2.0-ggml as the primary variant:** rejected for v1 because the model file is ~1.5 GiB resident vs. whisper.cpp medium-q5's ~0.9 GiB, and the 12 → 13 GiB Docker memory floor would have to rise to ~14 GiB to keep comfortable headroom. The faster-Japanese variant is a worthwhile follow-up once the plumbing is stable; the `ASR_MODEL` env var is the swap point.
- **faster-whisper (CTranslate2) Python service:** rejected — ~3.8 GiB RAM for the medium model on CPU (the Python + PyTorch runtime overhead dominates), which would force the Docker floor to ~15 GiB. Functionally fine, just costlier to host than whisper.cpp.
- **Co-locating whisper inside the backend container:** rejected — the DDD layer split (`backend/SPEC.md#layer-boundaries`) bans `domain/usecases` from talking to ML runtimes directly, and bundling whisper-server into the backend image bloats `backend` build time and re-arms G0 every time `backend/` changes. A separate service is the same shape as `llm`.
- **Whisper large-v3 (vanilla):** rejected for CPU — RTF of ~3-6× on a 4-core CPU means a 60s clip takes 3-6 minutes, well outside any reasonable `ASR_TIMEOUT_S`. Latency, not accuracy, is the binding constraint.
- **Streaming partial transcripts (chunked ASR):** rejected for v1 — adds substantial complexity (chunked upload + SSE response + reconciliation) for a feature whose primary value (replace typing with dictation) is fully delivered by non-streaming. Tracked as out-of-scope; revisit after first-cut ships.

## Gates affected

- **G0 (Compose-up):** new `asr` service added; healthcheck threshold remains ≤120 s post-first-boot. First boot bandwidth grows by ~0.7 GiB (model pull).
- **G4 (Security / PHI):** new clause forbidding audio egress + browser-storage. `security-check` grep matrix gains: `grep -RnE 'getUserMedia|MediaRecorder|webkitSpeechRecognition' frontend/src` outside `voice/` molecules is suspicious; `grep -RnE 'asr|whisper' backend/app | grep -v '^backend/app/infrastructure/asr/'` is a G7 architecture failure.
- **G5 (Cost / Inference budget):** new latency budget for ASR — `ASR_TIMEOUT_S=90` default, p95 ≤45 s for a 60 s clip on the reference hardware. Co-resident memory budget: gemma4:e4b (10 GiB) + whisper.cpp medium-q5 (1 GiB) + overhead (2 GiB) = 13 GiB. This is the operational ask for the Docker memory slider.
- **G7 (Architecture):** new `app/infrastructure/asr/` directory; `LocalASRClient` Protocol; `OllamaLocalLLMClient` precedent applies — `usecases` only constructs/invokes via factory; `domain` stays ASR-free.

## Open follow-ups

- [x] Once this ADR is `Accepted`, human edits `.claude/rules/local-llm-and-phi.md` §3 to add audio to the PHI enumeration and §1 to add ASR to the network-egress clause. (Agents cannot do this edit per `AGENTS.md` §3.)
- [x] Generator implements `INF-004` (compose `asr` service), `BE-014` (ASR adapter + transcribe endpoint), `FE-009` (RecordButton atom + VoiceCapture molecule + draft-page wiring) per the Block handoff that references this ADR.
- [x] cost-check is invoked once a real recording exists in the dev environment to verify p95 latency and co-resident memory stay inside the budget.
- [x] Re-evaluate the variant after first user feedback. If Japanese WER on whisper.cpp medium-q5 is too low to be useful (clinicians abandoning the feature), flip `ASR_MODEL` to `kotoba-whisper-v2.0-ggml` via a follow-up ADR and raise the memory floor to ≥14 GiB.
- [x] Add a Playwright-tagged integration test for the microphone-permission-denied path once FE-009 lands.
