---
name: security-check
description: Run PHI-egress and rule-conformance checks on the current repo state. Owns G4. Produces a structured findings report. Use when a Block has `Inference Impact: yes` or `Data Sensitivity: PHI`, or whenever a commit touches the inference layer / PHI surfaces.
---

# security-check

**Project rule this skill enforces:** `.claude/rules/local-llm-and-phi.md` — PHI must not leave the local Docker network.

This skill replaces the legacy `security-check` subagent. It is a deterministic recipe: caller has Bash + Read, runs the grep matrix and the inspection checks below, classifies findings by severity, and returns a structured report in the handoff envelope.

## When to use

- Generator self-evals **before** handing off to Evaluator on any Block where `Inference Impact: yes` OR `Data Sensitivity: PHI`.
- Evaluator re-runs the same matrix during QA on the same Block class (redundant by design — independent verification).
- Main loop runs it ad-hoc when a security concern surfaces outside the Block flow (e.g. a dependency bump on a non-PHI Block that still warrants a scan).

## Focus areas (severity priors)

1. **PHI in logs.** Any `logger.*` / `print` / `console.log` / unmasked exception that touches a request body, prompt, or model response involving PHI is **CRITICAL**.
2. **Inference-layer boundary.** Direct LLM/ASR calls outside `backend/app/infrastructure/llm/` or `backend/app/infrastructure/asr/` are **CRITICAL** (e.g. `httpx.post("http://llm:11434...")`, `requests.post(...)`, `fetch("http://llm...")`, `fetch("http://asr...")`).
3. **Hosted-LLM / hosted-ASR dependencies.** Presence of `openai`, `@anthropic-ai/sdk`, `@google/generative-ai`, `@aws-sdk/client-bedrock`, `langchain-openai`, `deepgram`, `assemblyai`, `@aws-sdk/client-transcribe`, `@azure/cognitiveservices-speech-sdk`, `@google-cloud/speech`, etc. is **CRITICAL**.
4. **Browser Web Speech API.** `webkitSpeechRecognition`, `window.SpeechRecognition`, `SpeechRecognition` references anywhere in `frontend/src/` are **CRITICAL** — they send audio to vendor servers.
5. **Compose egress.** `docker-compose.yml` must not publish `llm`, `postgres`, or `asr` ports to the host, must not set `extra_hosts` to public IPs, and must keep these services on the `internal` network. Frontend may publish 3000; backend may publish 8000.
6. **Frontend storage of PHI.** PHI written to `localStorage`, `sessionStorage`, or `IndexedDB` is **CRITICAL**. Audio Blobs and ASR transcripts inherit this rule.
7. **API responses.** Endpoints returning PHI fields the caller did not explicitly request — **WARNING** (becomes **CRITICAL** if combined with weak auth).
8. **Pydantic at boundaries.** Untyped `dict` flowing into a router from external input — **WARNING**.
9. **MediaRecorder / getUserMedia outside voice components.** Frontend mic capture references outside the dedicated voice modules — **CRITICAL** (per ADR-0001).
10. **PR-body PHI leakage.** Raw PHI tokens (patient names, MRNs, DOBs, addresses) in a PR title or body — **CRITICAL**. The PR body is reviewed in GitHub's UI; treat it as a public log surface even though the repo is private, on the same footing as a `logger.info` call. References by Block ID, by fixture name, or by structural anchor are PASS. (Added by ADR-0005.)

## Verification commands

Run these via Bash and capture output. Annotate each with PASS / FAIL.

```bash
# Probe 1 — Hosted-LLM SDKs in frontend deps
grep -E '"(openai|@anthropic-ai|@google/generative-ai|@aws-sdk/client-bedrock|cohere|replicate)"' frontend/package.json && exit 1 || echo "clean"

# Probe 2 — Hosted-LLM SDKs in backend deps
grep -Ei 'openai|anthropic|google-generativeai|bedrock|cohere|replicate' backend/requirements.txt backend/pyproject.toml 2>/dev/null && exit 1 || echo "clean"

# Probe 3 — Direct LLM calls outside infrastructure layer
grep -RnE 'http://llm[: ]|ollama' backend/app | grep -v '^backend/app/infrastructure/llm/' && exit 1 || echo "clean"

# Probe 4 — Compose egress (extra_hosts / host.docker.internal / forbidden port publishes)
grep -nE 'extra_hosts|host\.docker\.internal|"5432:5432"|"11434:11434"' docker-compose.yml && exit 1 || echo "clean"

# Probe 5 — Hosted-ASR SDKs (frontend + backend) — ADR-0001
grep -E '"(deepgram|assemblyai|@aws-sdk/client-transcribe|@azure/cognitiveservices-speech-sdk|@google-cloud/speech)"' frontend/package.json backend/requirements.txt && exit 1 || echo "clean"

# Probe 6 — Browser Web Speech API anywhere in frontend
grep -RnE 'webkitSpeechRecognition|window\.SpeechRecognition|\bSpeechRecognition\b' frontend/src && exit 1 || echo "clean"

# Probe 7 — Direct ASR calls outside infrastructure layer
grep -RnE 'http://asr[: ]|whisper' backend/app | grep -v '^backend/app/infrastructure/asr/' && exit 1 || echo "clean"

# Probe 8 — MediaRecorder / getUserMedia outside dedicated voice modules
grep -RnE 'getUserMedia|MediaRecorder' frontend/src | grep -vE '(VoiceCapture|RecordButton|useVoiceCapture)' && exit 1 || echo "clean"

# Probe 9 — PHI in logs near patient/encounter/record endpoints (inspect each hit manually)
grep -RnE 'logger\.(info|warning|error)\(|print\(' backend/app | grep -Ei 'patient|mrn|encounter|record'

# Probe 10 — Frontend PHI storage
grep -RnE '\b(localStorage|sessionStorage|indexedDB)\b' frontend/src

# Probe 10b — PHI in React state (ADR-0004): PHI buffers must live in useRef, not useState.
# Audio blobs, partial transcripts, chunk accumulation, SSE draft buffers are all PHI.
# Inspect each hit manually — flag any useState holding audio/transcript/chunk content.
grep -RnE 'useState[<(][^)>]*[Pp]artial|useState[<(][^)>]*[Tt]ranscript|useState[<(][^)>]*[Cc]hunk[A-Z]|useState[<(][^)>]*[Aa]udio' frontend/src/hooks frontend/src/components 2>/dev/null

# Probe 11 — PR-body / PR-title PHI scan (run before opening a PR; ADR-0005)
# If `gh` is installed AND the PR is already drafted:
#   gh pr view --json title,body --jq '.title, .body'
# If not yet pushed, render the body locally before push and grep it:
#   cat /tmp/pr-body.md
# Inspect each hit manually. Raw patient names, MRNs, DOBs, addresses in PR title or body
# are CRITICAL. References by Block ID, fixture name, or structural anchor are PASS.

# Probe 12 — ADR-0006: frontend に dd-trace (Node) を入れない
grep -RE 'dd-trace' frontend/src && echo "CRITICAL: dd-trace in frontend" || echo "clean"

# Probe 13 — ADR-0006: frontend src には OTel browser SDK は入らない
grep -RE '@opentelemetry' frontend/src && echo "CRITICAL: OTel browser SDK in frontend" || echo "clean"

# Probe 14 — ADR-0006 FE-015: Datadog Browser RUM SDK isolation
grep -RE '@datadog/browser-' frontend/src | grep -vE '(lib/datadog-rum|components/_rum)' \
  && echo "CRITICAL: RUM SDK leaked outside designated files" || echo "clean"

# Probe 15 — ADR-0006 FE-015: RUM init defaults hardcode 検証
grep -c 'defaultPrivacyLevel: "mask"' frontend/src/lib/datadog-rum.ts | grep -E '^1$' \
  || echo "CRITICAL: defaultPrivacyLevel must be exactly 'mask', once"
grep -c 'trackLongTasks: false' frontend/src/lib/datadog-rum.ts | grep -E '^1$' \
  || echo "CRITICAL: trackLongTasks must be false, once"
grep -c "id: \"anon\"" frontend/src/lib/datadog-rum.ts | grep -E '^1$' \
  || echo "CRITICAL: setUser must be called exactly once with id:'anon'"
```

For probes 9, 10, and 11, hits are not automatic failures — inspect each line. PHI variables passed to log calls, storage APIs, or PR titles/bodies without `mask_phi`/`maskPhi` are CRITICAL.

## Output format

```
## Security Findings: <task-id>

- **Goal:** Report PHI-egress and rule-conformance state for this Block.
- **Inputs:** .claude/rules/local-llm-and-phi.md; <diff or commit>; docker-compose.yml; dependency manifests.
- **Acceptance:**
  - [ ] No CRITICAL findings.
  - [ ] All WARNING findings have a documented mitigation or are accepted via ADR.
- **Out-of-scope:** General hardening unrelated to PHI/inference.
- **Open-questions:** _(none)_
- **Findings:**
  - [CRITICAL] <one-line summary> — file/line; attack vector: <one line>; fix: <one line>.
  - [WARNING] …
  - [ADVICE] …
- **Net verdict:** PASS | FAIL
```

A single CRITICAL = FAIL. WARNING does not auto-fail but blocks Done unless the Block carries an ADR reference accepting it.

## Escalation

If the Block as written requires hosted-LLM / hosted-ASR capabilities the local stack cannot provide, do not propose a hosted fallback. Return FAIL and recommend Planner amend the Spec or scope.

## Anti-patterns

- Reporting "looks fine" without running the probe matrix.
- Treating logged PHI as low-severity because it is "only local". A local laptop is a stolen-device target.
- Approving a direct `httpx` / `fetch` call to the LLM or ASR service from a non-infrastructure layer because "it's small". The boundary is the rule.
- Skipping probes because "no audio code in this Block" — Probes 5–8 are cheap; running them confirms the diff didn't accidentally introduce one.
