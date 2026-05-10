# AGENTS.md

Cross-agent rules. Every agent (Planner, Generator, Evaluator, cost-check, security-check, plus any future role) reads this file at the start of every session. Claude-Code-specific behaviour belongs in `CLAUDE.md`; everything in this file applies regardless of which harness is driving.

## 1. Roles at a glance

| Agent              | Model  | Reads                                                                             | Writes                                           | Hands off to                          |
| ------------------ | ------ | --------------------------------------------------------------------------------- | ------------------------------------------------ | ------------------------------------- |
| **Planner**        | Opus   | SPEC.md (root + sub), DESIGN.md, NOTES.md, ADRs, .claude/rules/                   | SPEC.md (root + sub), NOTES.md, new ADRs         | Generator                             |
| **Generator**      | Sonnet | SPEC.md, TASKS.md, DESIGN.md, .claude/rules/, source code                         | TASKS.md, source code, tests, docker-compose.yml | security-check, cost-check, Evaluator |
| **Evaluator**      | Opus   | SPEC.md, TASKS.md, source code, security-check report, cost-check report          | QA Failure Block (handoff), commit on pass       | Generator (fail), Planner (pivot)     |
| **security-check** | Opus   | source code, docker-compose.yml, .claude/rules/local-llm-and-phi.md, dependencies | structured findings report                       | caller                                |
| **cost-check**     | Opus   | SPEC.md (latency/VRAM budgets), source code, docker compose logs                  | structured cost report                           | caller                                |

## 2. The contract every agent obeys

- Every Spec section, every Task entry, and every inter-agent prompt is a Block per `docs/handoff-contract.md`. Free-form prose is not a valid handoff.
- Every Done claim is gated by `docs/dod-and-gates.md`. Skipping a gate is a process failure regardless of the implementation's quality.
- Every PHI- or inference-touching change obeys `.claude/rules/local-llm-and-phi.md`. No exceptions, no inline overrides — only ADRs.

## 3. File ownership

A file's owner is the agent that may modify it. Other agents may read.

| Path                                             | Owner               | Notes                                                                            |
| ------------------------------------------------ | ------------------- | -------------------------------------------------------------------------------- |
| `SPEC.md`, `frontend/SPEC.md`, `backend/SPEC.md` | Planner             | Generator MAY append `## Open-questions` Blocks; never edit existing Acceptance. |
| `TASKS.md` (each)                                | Generator           | Planner seeds the first set; Generator owns updates thereafter.                  |
| `NOTES.md`                                       | Planner             | Generator and Evaluator MAY add evidence bullets only.                           |
| `docs/adr/*.md`                                  | Author named in ADR | Status changes require Planner sign-off.                                         |
| `DESIGN.md`                                      | Planner             | Generator proposes via ADR; never edits in-place for design rules.               |
| `.claude/agents/*.md`                            | Human only          | Agents do not self-modify their own role definitions.                            |
| `.claude/rules/*.md`                             | Human only          | Changes require an ADR.                                                          |
| `.claude/settings.json`, hooks                   | Human only          | Out of bounds for all agents.                                                    |
| Source code, tests, `docker-compose.yml`         | Generator           | Evaluator may read and run; never edits.                                         |

## 4. Language rules

- Code identifiers and API field names: English.
- UI display strings: Japanese.
- Code comments: Japanese (per CLAUDE.md). Keep them about _why_; do not narrate _what_.
- Docs in this repo: English. Concise. No marketing tone.
- Human chat in the harness: Japanese (per CLAUDE.md).
- Commit messages: English, imperative, ≤72 chars subject; body when the diff alone does not explain the why.

## 5. Refusal & escalation

An agent MUST refuse to act and bounce a handoff back when:

- The Block violates `docs/handoff-contract.md` §6.
- Acting would violate `.claude/rules/local-llm-and-phi.md`.
- A pre-condition gate per `docs/dod-and-gates.md` has not been run by its owner.

An agent escalates to Planner via the Spec Pivot Request shape when:

- Two consecutive Generator iterations fail the same gate for the same root cause.
- A Spec Acceptance item is provably unachievable on the assumed hardware (`SPEC.md#hardware-assumptions`).
- A new constraint surfaces that was not contemplated in the originating Spec.

## 6. Self-evaluation discipline

- Generator MUST run G0–G3 to green before invoking Evaluator. Self-evaluation is not commentary on quality; it is gate execution.
- Evaluator MUST NOT re-run G0–G3 as if they had not been done. If the Evaluator finds them broken, it returns a QA Failure Block citing G1/G2/G3 — it does not silently fix.
- Neither agent grades its own work for spec alignment. G6 is Evaluator-only.

## 7. Token & cost discipline

- Default to Sonnet; promote to Opus only for Planner/Evaluator roles or for genuinely novel design work.
- Reuse existing Blocks by reference (`SPEC.md#section`) rather than copy-pasting their content into prompts.
- Do not echo file contents back to the human after a successful edit; the diff is canonical.
- cost-check is the agent that owns this section operationally; everyone else applies the spirit.

## 8. Commit & branching

- One feature Block ≈ one commit. The commit subject names the Block ("Patient search by MRN" → `feat: patient search by MRN`).
- Generator commits after self-eval is green and BEFORE invoking Evaluator. Evaluator commits a tag/marker on pass; on fail, the Generator's commit stays as the work-in-progress record.
- Never amend a commit that has been handed to the Evaluator. Add a follow-up commit instead.
- Never `git push` from any agent. The human pushes.

## 9. Things every agent should keep visible

- Latency budget and PHI rule are the two cliffs everyone falls off first; check both before declaring Done.
- An empty `Out-of-scope` field is almost always a sign the Block has not been thought through.
- A change that touches `docker-compose.yml` re-arms G0; Generator MUST re-run it.
- An ADR is cheap. Use one whenever a decision will outlast the current task.
