# Rule: Local LLM & PHI Handling

This rule is non-negotiable. It binds every agent (Planner, Generator, Evaluator, cost-check, security-check) and every code change. Violations stop the harness loop and require an ADR before resuming.

## 1. Network egress

- All inference calls MUST go to the in-network `llm` service (`http://llm:11434`). The hostname is `llm`, never `localhost` or a public domain.
- No code path may import or call a hosted-LLM SDK (OpenAI, Anthropic, Google AI, Bedrock, Azure OpenAI, etc.) at runtime. Detection of such an import is a CRITICAL G4 finding.
- The `docker-compose.yml` MUST NOT publish the `llm` or `postgres` ports to the host. Internal-only.
- The backend container MUST NOT define `extra_hosts` that resolve to public IPs.
- All ASR (audio transcription) calls MUST go to the in-network `asr` service (`http://asr:<port>`). The hostname is `asr`, never `localhost` ora public domain.
- No code path may use the browser Web Speech API (`webkitSpeechRecognition`, `window.SpeechRecognition`) or any hosted ASR SDK (Deepgram, AssemblyAI, Azure Speech, Google Cloud Speech, Amazon Transcribe). Detection of such an import or API reference is a CRITICAL G4 finding.
- The `docker-compose.yml` MUST NOT publish the `asr` port to the host. Internal-only.

## 2. Inference layer boundary

- All inference calls go through `app/infrastructure/llm/`. The class implementing the call is `LocalLLMClient` (interface) with a concrete `OllamaLocalLLMClient` and a test-only `FakeLocalLLMClient`.
- `app/domain/` MUST NOT import from `app/infrastructure/`. Domain stays inference-free.
- `app/usecases/` is the only layer that may construct or invoke an `LocalLLMClient`.
- All ASR calls go through `app/infrastructure/asr/`. The class implementing the call is `LocalASRClient` (interface) with a concrete
  `WhisperCppLocalASRClient` and a test-only `FakeLocalASRClient`. A direct `httpx.post("http://asr:...")` outside `app/infrastructure/asr/` is a G7 architecture failure even if functionally correct.
- A direct `httpx.post("http://llm:...")` outside `app/infrastructure/llm/` is a G7 architecture failure even if functionally correct.

## 3. PHI in prompts

PHI = any of: patient name, MRN, DOB, address, phone, free-text clinical narrative, lab values tied to identity.

- PHI in a prompt is allowed because the model is local. PHI in a _log line_ is not.
- Before any `logger.info` / `logger.warning` / `print` / `console.log` of an inference request or response, run the value through the masking utility (`mask_phi(...)` backend, `maskPhi(...)` frontend).
- Stack traces from inference exceptions MUST scrub the prompt body. Use the masked-exception wrapper, not the raw exception.
- Tests MAY use synthetic-only PHI fixtures. Real PHI MUST NOT enter the repo.
- Audio bytes, audio file names, and ASR transcripts MUST NOT appear in logs. Mask via `mask_phi(...)` (backend) / `maskPhi(...)` (frontend) on any reference. Audio MUST NOT be persisted to disk past the request lifetime; never to DB; never to browser storage. ASR transcripts inherit the same masking expectation as `clinical_input`.

## 4. PHI in storage and transit

- PHI persisted in Postgres uses the same masked-on-read path for analytic queries. Operational reads stay unmasked but are gated by usecase-level authorisation.
- HTTP responses to the frontend MUST NOT include PHI fields the caller has not explicitly requested. Default-deny on serializer fields.
- The frontend MUST NOT write PHI to `localStorage`, `sessionStorage`, or IndexedDB. Memory only.
- **PHI-bearing buffers and accumulators MUST live in `useRef`** (or equivalent stable, non-snapshot storage) — not `useState`. Examples: audio Blob, chunked partial transcripts, accumulated SSE chunks before completion, streaming-draft buffer before final `setDraft`. React DevTools' Hooks Inspector captures `useState` values in real time; `useRef` is intentionally outside React's reconciliation snapshot. (ADR-0004)
- **Counters, status flags, and structural metadata MAY live in `useState`** because they contain no PHI: `chunkIndex: number`, `chunkCount: number | null`, `status: "uploading" | "success" | ...`, `elapsedMs: number`.
- When a component needs to **display** the buffered PHI content, the rendered string MUST be derived at render time from the `useRef` content. Typical pattern: `useState<number>` tick counter incremented per chunk arrival forces a re-render; the component reads `ref.current.join("")` on every render.
- **Backend buffers:** PHI bytes/text MUST NOT be added to long-lived dataclasses or attribute slots accessible via `repr`/`str`. Use locally-scoped `list[str]` or `bytearray` inside the function scope and explicitly drop the reference when the stream completes.

## 5. Refusal triggers for agents

The Generator MUST refuse the task and bounce it back to Planner when:

- A SPEC Block sets `Data Sensitivity: PHI` but does not specify masking expectations.
- A SPEC Block sets `Inference Impact: yes` but does not pin the model variant or the latency budget.
- A SPEC Block describes a feature that fundamentally requires hosted-LLM-only capabilities (e.g. multimodal beyond what local Gemma supports). Generator does not silently substitute.

## 6. Verification commands

`security-check` runs at minimum:

```bash
# No hosted-LLM SDKs in dependencies.
grep -E '"(openai|@anthropic-ai|@google/generative-ai|@aws-sdk/client-bedrock)"' frontend/package.json backend/requirements.txt && exit 1 || true

# No direct LLM calls outside the infrastructure layer.
grep -RE 'http://llm[: ]|ollama' backend/app | grep -v '^backend/app/infrastructure/llm/' && exit 1 || true

# No public-internet egress in compose.
grep -E 'extra_hosts|host.docker.internal' docker-compose.yml || true

# No hosted-ASR SDKs in dependencies.
grep -E '"(deepgram|assemblyai|@aws-sdk/client-transcribe|@azure/cognitiveservices-speech-sdk|@google-cloud/speech)"' frontend/package.json backend/requirements.txt && exit 1 || true

# No browser Web Speech API.
grep -RE 'webkitSpeechRecognition|window\.SpeechRecognition' frontend/src && exit 1 || true

# No direct ASR calls outside the infrastructure layer.
grep -RE 'http://asr[: ]|whisper' backend/app | grep -v '^backend/app/infrastructure/asr/' && exit 1 || true

# Frontend mic capture stays in dedicated voice components.
grep -RE 'getUserMedia|MediaRecorder' frontend/src | grep -vE '(VoiceCapture|RecordButton|useVoiceCapture)' && exit 1 || true
```

A non-clean result on any of the first two is CRITICAL.

## 7. Changing this rule

A change to any clause requires:

1. An ADR in `docs/adr/`.
2. Approval recorded as the ADR's Status field flipping to Accepted.
3. The corresponding handoff that referenced the old rule is invalidated; Planner re-issues.
