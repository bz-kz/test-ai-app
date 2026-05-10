# Definition of Done & Quality Gates

A task is **Done** only when every gate below passes for the changes it touches. Gates run in order; later gates assume earlier gates have passed. Each gate has a single owner role and a hard, machine-checkable threshold.

## Gate table

| Gate   | Name                    | Owner          | Hard threshold                                                                                                                                    | Verification command                                                                                  |
| ------ | ----------------------- | -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| **G0** | Compose-up              | Generator      | `docker compose up -d` returns success and every service reports healthy within 120 s.                                                            | `docker compose up -d && docker compose ps --status running`                                          |
| **G1** | Type                    | Generator      | 0 errors.                                                                                                                                         | Frontend: `cd frontend && npx tsc --noEmit`. Backend: `cd backend && pyright`.                        |
| **G2** | Lint / Format           | Generator      | 0 errors. Format clean.                                                                                                                           | Frontend: `npx eslint . && npx prettier --check .`. Backend: `ruff check . && ruff format --check .`. |
| **G3** | Unit                    | Generator      | All affected unit tests green. New behaviour has at least one test. Inference layer mocked via `FakeLocalLLMClient`.                              | Frontend: `npm test -- --run`. Backend: `pytest -q`.                                                  |
| **G4** | Security / PHI          | security-check | 0 CRITICAL findings. PHI never leaves the local Docker network. Logs mask PHI.                                                                    | `security-check` agent report; `grep -R` for direct LLM calls outside `app/infrastructure/llm/`.      |
| **G5** | Cost / Inference budget | cost-check     | Latency p95 within Spec budget. VRAM peak within Spec budget. Model tier matches Spec.                                                            | `cost-check` agent report; runtime traces from `docker compose logs`.                                 |
| **G6** | Spec alignment          | Evaluator      | Every Acceptance item in the originating SPEC Block is checked. No silent scope changes.                                                          | Evaluator reads SPEC Block + diff and ticks each item.                                                |
| **G7** | Architecture            | Evaluator      | Frontend: Atomic Design layer placement correct; logic out of components. Backend: DDD direction respected — domain has no infra/usecase imports. | `grep`/`madge`-style import-direction checks; manual review against the layer matrix in CLAUDE.md.    |

## Gate ownership rules

- **Generator** runs G0–G3 as self-evaluation BEFORE invoking Evaluator. Skipping is a process failure regardless of the implementation's quality.
- **security-check** and **cost-check** are mid-flight gates. Generator MAY invoke them during implementation; Evaluator MUST require their reports for any task with `Inference Impact: yes` or `Data Sensitivity: PHI`.
- **Evaluator** runs G6–G7 last. Earlier gates being green is a precondition; Evaluator does not duplicate that work.

## Gate-failure protocol

A failed gate stops forward motion. The agent that detected the failure returns a `## QA Failure` Block per `docs/handoff-contract.md` §4. The receiving agent does NOT begin a new fix until the failure Block lists every failed gate, not just the first.

## Per-task gate selection

Each Spec/Task Block declares `Gates Touched`. A task that does not touch a gate (e.g. a docs-only change skips G0/G3) MUST still pass the gates it does touch. The default for any code change is `G1, G2, G3, G6, G7`. Add G0 for compose-affecting changes, G4 for any PHI/inference work, G5 for any latency/VRAM-affecting work.

## What is NOT a gate

- Subjective UI polish — covered by DESIGN.md and reviewed visually.
- Documentation updates — required by the handoff contract, but not gated.
- Commit message style — required by `AGENTS.md`, but not gated.

## When gates conflict with delivery pressure

There is no override. If a gate cannot pass, escalate to Planner via the Spec Pivot Request shape (handoff contract §5) and adjust scope. Bypassing a gate to ship is the single fastest way to introduce a PHI leak or break the harness loop.
