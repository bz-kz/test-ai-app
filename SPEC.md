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

## Hardware Assumptions

- **Goal:** State the baseline so latency and VRAM budgets in feature Specs are interpretable.
- **Inputs:** _(none)_
- **Acceptance:**
  - [ ] Reference dev hardware: 8-core CPU, 16 GB RAM, single GPU with ≥6 GB VRAM (e.g. RTX 4060). E4B fits on modest hardware by design.
  - [ ] CPU-only operation supported; latencies SHOULD assume ≥3× slowdown vs GPU baseline.
  - [ ] Latency budget for `gemma4:e4b` first-token: p95 ≤1 s; total response p95 ≤6 s for 1k output tokens.
  - [ ] VRAM peak: ≤6 GB at `gemma4:e4b` Q4_0.
- **Out-of-scope:** Multi-GPU, Apple-Silicon-specific tuning (track in a follow-up ADR if needed).
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
- **PHI:** Governed by `.claude/rules/local-llm-and-phi.md`. Masked in logs, never persisted in browser storage, never sent to a hosted LLM.
- **Determinism for tests:** All inference paths use `FakeLocalLLMClient` in unit tests; integration tests against the real `llm` container are tagged and excluded from the default `pytest`/`vitest` run.

## Living index

- Frontend Spec: `frontend/SPEC.md`
- Backend Spec: `backend/SPEC.md`
- Handoff contract: `docs/handoff-contract.md`
- Definition of Done & Gates: `docs/dod-and-gates.md`
- Local-dev runbook: `docs/runbook-local-dev.md`
- ADR index: `NOTES.md`
- PHI/LLM rule: `.claude/rules/local-llm-and-phi.md`
