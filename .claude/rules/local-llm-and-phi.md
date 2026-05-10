# Rule: Local LLM & PHI Handling

This rule is non-negotiable. It binds every agent (Planner, Generator, Evaluator, cost-check, security-check) and every code change. Violations stop the harness loop and require an ADR before resuming.

## 1. Network egress

- All inference calls MUST go to the in-network `llm` service (`http://llm:11434`). The hostname is `llm`, never `localhost` or a public domain.
- No code path may import or call a hosted-LLM SDK (OpenAI, Anthropic, Google AI, Bedrock, Azure OpenAI, etc.) at runtime. Detection of such an import is a CRITICAL G4 finding.
- The `docker-compose.yml` MUST NOT publish the `llm` or `postgres` ports to the host. Internal-only.
- The backend container MUST NOT define `extra_hosts` that resolve to public IPs.

## 2. Inference layer boundary

- All inference calls go through `app/infrastructure/llm/`. The class implementing the call is `LocalLLMClient` (interface) with a concrete `OllamaLocalLLMClient` and a test-only `FakeLocalLLMClient`.
- `app/domain/` MUST NOT import from `app/infrastructure/`. Domain stays inference-free.
- `app/usecases/` is the only layer that may construct or invoke an `LocalLLMClient`.
- A direct `httpx.post("http://llm:...")` outside `app/infrastructure/llm/` is a G7 architecture failure even if functionally correct.

## 3. PHI in prompts

PHI = any of: patient name, MRN, DOB, address, phone, free-text clinical narrative, lab values tied to identity.

- PHI in a prompt is allowed because the model is local. PHI in a _log line_ is not.
- Before any `logger.info` / `logger.warning` / `print` / `console.log` of an inference request or response, run the value through the masking utility (`mask_phi(...)` backend, `maskPhi(...)` frontend).
- Stack traces from inference exceptions MUST scrub the prompt body. Use the masked-exception wrapper, not the raw exception.
- Tests MAY use synthetic-only PHI fixtures. Real PHI MUST NOT enter the repo.

## 4. PHI in storage and transit

- PHI persisted in Postgres uses the same masked-on-read path for analytic queries. Operational reads stay unmasked but are gated by usecase-level authorisation.
- HTTP responses to the frontend MUST NOT include PHI fields the caller has not explicitly requested. Default-deny on serializer fields.
- The frontend MUST NOT write PHI to `localStorage`, `sessionStorage`, or IndexedDB. Memory only.

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
```

A non-clean result on any of the first two is CRITICAL.

## 7. Changing this rule

A change to any clause requires:

1. An ADR in `docs/adr/`.
2. Approval recorded as the ADR's Status field flipping to Accepted.
3. The corresponding handoff that referenced the old rule is invalidated; Planner re-issues.
