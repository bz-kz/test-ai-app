<!--
Pull-request template for the AI Medical Record Generator project.
Owned by ADR-0005; rendered by .claude/skills/git-pr-flow/SKILL.md.

Agents: fill every placeholder before opening the PR. Do not leave `<TBD>` anywhere
in the body — that is a Refusal trigger per docs/handoff-contract.md §6.

Humans: review the Acceptance checklist and Gates sections first. The Diff is the
ground truth; the body is the agent's summary of why this diff matches the Spec.
-->

## Block

- **Block ID(s):** <e.g. `BE-018`, `FE-013` — list all Blocks this PR closes>
- **Block title(s):** <copy from SPEC.md or TASKS.md row>

## Summary

<One paragraph. The outcome (what this PR causes to happen), not the implementation steps.
Implementation lives in the diff; the PR body is the why.>

## Acceptance (from SPEC Block)

Copy the Acceptance bullets from the SPEC Block(s) verbatim and tick them as the implementation satisfies each. Untickable items are a Refusal trigger (Generator: do not open a PR with unchecked Acceptance rows unless the PR is `--draft` and that Block is explicitly multi-PR).

- [ ] <criterion 1>
- [ ] <criterion 2>
- [ ] <criterion 3>

## SPEC and ADR references

- **SPEC:** <path>#<anchor> (e.g. `backend/SPEC.md#asr-adapter`)
- **ADRs:** <list all ADRs this PR implements, references, or is gated by — e.g. `docs/adr/0003-streaming-asr-chunked.md`>
- **TASKS:** <`TASKS.md` row id(s) this PR moves to `done` — e.g. `BE-018`>

## Gates passed

| Gate                  | Status     | Evidence                                                                                |
| --------------------- | ---------- | --------------------------------------------------------------------------------------- |
| G0 Compose-up         | PASS / N/A | <command + observed time, or "N/A — no compose change">                                 |
| G1 Type               | PASS       | <`npx tsc --noEmit` exit 0 / `pyright` exit 0>                                          |
| G2 Lint               | PASS       | <`npx eslint .` 0 errors / `ruff check .` exit 0>                                       |
| G3 Unit               | PASS       | <`npm test -- --run` N tests / `pytest -q` N tests passed>                              |
| G4 Security (PHI/inf) | PASS / N/A | <embed `security-check` Findings below, or "N/A — Block is not PHI/inference touching"> |
| G5 Cost (latency)     | PASS / N/A | <embed `cost-check` Findings below, or "N/A — Block has no inference impact">           |
| G6 Spec align         | PENDING    | <left for Evaluator after merge — typically blank at PR-open time>                      |
| G7 Architecture       | PENDING    | <left for Evaluator — typically blank at PR-open time>                                  |

### security-check Findings (only when Block touches PHI or inference)

<Embed the structured Findings block from the security-check skill output verbatim. Net verdict at the bottom. Omit this whole subsection when the Block is not PHI/inference touching — replace with "_(not applicable for this Block)_".>

### cost-check Findings (only when Block has `Inference Impact: yes`)

<Embed the structured Findings block from the cost-check skill output verbatim. Observed latency and RAM numbers against thresholds. Omit this whole subsection when the Block has no inference impact — replace with "_(not applicable for this Block)_".>

## Test counts

- **Frontend:** <N tests, M new, K updated. "0 new" is acceptable when the Block is non-frontend.>
- **Backend:** <N tests, M new, K updated. "0 new" is acceptable when the Block is non-backend.>

## Playwright UI verification (only when Block is UI-touching)

<Embed the `## Playwright UI Verification` section the main loop / Generator captured pre-PR. This is the same content the Evaluator reads per the Evaluator agent definition. Omit when the Block has no UI surface — replace with "_(not applicable for this Block)_".>

## Deployment notes

`N/A — local PoC` is the standard answer. If the Block changed `docker-compose.yml`, list the new env vars, new services, new ports, or new healthchecks here.

## Out-of-scope (carried from the SPEC Block)

- <bullet 1 — carry from the SPEC Block's Out-of-scope list>
- <bullet 2>

## Open questions

If everything in the originating SPEC Block was resolved, write `_(none)_`. A non-empty list here is a signal that the Block was not fully closed and the PR should be `--draft`.

- _(none)_
