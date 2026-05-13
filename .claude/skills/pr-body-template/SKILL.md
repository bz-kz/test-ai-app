---
name: pr-body-template
description: Fill-in template for PR bodies opened by agents via `gh pr create --body-file`. Companion to git-pr-flow (the gh CLI recipe) and `.github/pull_request_template.md` (the GitHub UI auto-fill). Use when constructing the body markdown for a Block PR; this skill provides the section schema, fill-in rules, and worked examples lifted from past Blocks.
---

# pr-body-template

This skill provides the recipe for filling the PR body when an agent opens a pull request via `gh pr create --body-file <path>`. It mirrors `.github/pull_request_template.md` (the GitHub-side auto-fill that surfaces for human-initiated PRs) so the same body structure reaches reviewers regardless of which path opens the PR.

Authorized by ADR-0005. Recipe-only — hard rules (no merge, no force-push, no push-to-main) stay in `AGENTS.md` §8.

## When to use

- Generator (or main loop) is about to open a PR for a Block whose self-eval is green.
- Per ADR-0005 branch strategy: feature-class Blocks (`feat:` / `fix:` / `refactor:` ≥3 files) get their own PR; chore / docs / test Blocks batch onto the working branch and PR when the branch is ready.
- The `gh` CLI is installed and authenticated (`gh auth status` → logged in). If not, fall back to surfacing the rendered body to the user per `git-pr-flow` skill.

## Template (canonical)

The canonical template lives in `.github/pull_request_template.md`. Read it before constructing the body. The skeleton below is the same content with section-level fill-in instructions per agent role.

```markdown
## Block

- **Block ID(s):** <BE-NNN / FE-NNN / INF-NNN — list all Blocks this PR closes>
- **Block title(s):** <copy verbatim from SPEC.md or TASKS.md row>

## Summary

<One paragraph. Outcome (what this PR causes to happen), not implementation steps.
Implementation lives in the diff; the body is the why.>

## Acceptance (from SPEC Block)

Copy verbatim from the SPEC Block. Tick each item the implementation satisfies.

- [ ] <criterion 1>
- [ ] <criterion 2>

## SPEC and ADR references

- **SPEC:** <path>#<anchor>
- **ADRs:** <list>
- **TASKS:** <row id(s) moved to done>

## Gates passed

| Gate                  | Status     | Evidence                         |
| --------------------- | ---------- | -------------------------------- |
| G0 Compose-up         | PASS / N/A | <command + time, or "N/A">       |
| G1 Type               | PASS       | <command + 0 errors>             |
| G2 Lint               | PASS       | <command + 0 errors>             |
| G3 Unit               | PASS       | <N tests passed>                 |
| G4 Security (PHI/inf) | PASS / N/A | <see Findings below, or "N/A">   |
| G5 Cost (latency)     | PASS / N/A | <see Findings below, or "N/A">   |
| G6 Spec align         | PENDING    | <left for Evaluator after merge> |
| G7 Architecture       | PENDING    | <left for Evaluator>             |

### security-check Findings

<Embed the structured Findings block from the security-check skill output verbatim.
Net verdict at bottom. Omit this section when not PHI/inference touching — replace
with "_(not applicable for this Block)_".>

### cost-check Findings

<Embed the structured Findings block from the cost-check skill output verbatim.
Omit when no inference impact — replace with "_(not applicable for this Block)_".>

## Test counts

- **Frontend:** <N tests, M new, K updated>
- **Backend:** <N tests, M new, K updated>

## Playwright UI verification

<Embed the Playwright UI Verification section pre-PR. Omit if non-UI Block.>

## Deployment notes

`N/A — local PoC` is the standard answer. If docker-compose.yml changed: list env vars, services, ports, healthchecks.

## Out-of-scope (carried from SPEC Block)

- <bullet 1>
- <bullet 2>

## Open questions

`_(none)_` when the originating SPEC Block was fully resolved. A non-empty list means the PR should be `--draft`.

- _(none)_
```

## Fill-in rules (binding)

1. **No `<TBD>` / `<placeholder>` / `<see above>` in the final body.** Every angle-bracket marker MUST be replaced with concrete content or the section omitted with `_(not applicable for this Block)_`. Unresolved markers are a Refusal trigger per `docs/handoff-contract.md` §6.
2. **Acceptance bullets are verbatim from the SPEC Block.** Do not paraphrase, re-order, or merge bullets. The reviewer cross-references against `SPEC.md`; mismatches signal scope drift.
3. **G6 and G7 status stays `PENDING`** at PR-open time. These are Evaluator-owned gates that run on the post-merge tree (or on the PR after the Evaluator has reviewed the diff). The Generator MUST NOT set them PASS pre-merge.
4. **Findings blocks are verbatim from the skill output.** If you summarise or trim a `security-check` or `cost-check` Finding, you've lost the audit trail. Paste exactly.
5. **The PR title is the lead commit's conventional-subject.** Use the same string as `git log -1 --format=%s`. Do NOT prefix with `[BE-NNN]` or `(WIP)` — the Block ID is in the body, the WIP signal is `--draft`.
6. **No `🤖 Generated with Claude Code` footer.** Authorship is recorded by the commit's `Co-Authored-By: Claude <model>` trailer; duplicating in the PR body is noise.

## Worked example — feature Block (BE-014 ASR adapter, hypothetical)

```markdown
## Block

- **Block ID(s):** BE-014
- **Block title(s):** ASR adapter + transcribe endpoint

## Summary

Adds the backend side of voice transcription. Introduces `app/infrastructure/asr/` (mirroring `app/infrastructure/llm/`), wires `POST /encounters/{id}/transcribe` (multipart audio in, JSON transcript out), and keeps every audio byte in memory through the request lifetime. PHI rule §3 applies: no audio in logs, no audio on disk past the request.

## Acceptance (from SPEC Block)

- [x] `app/infrastructure/asr/` package exists with Protocol + concrete + fake
- [x] `transcribe_audio` usecase has no DB writes, no audit row
- [x] POST endpoint maps errors per SPEC: 401/404/415/422/503/504
- [x] 32 new unit tests across 4 layers

## SPEC and ADR references

- **SPEC:** `backend/SPEC.md#asr-adapter`, `backend/SPEC.md#transcribe-endpoint`
- **ADRs:** `docs/adr/0001-voice-input-and-local-asr.md`
- **TASKS:** `backend/TASKS.md` BE-014 → `done`

## Gates passed

| Gate          | Status  | Evidence                                           |
| ------------- | ------- | -------------------------------------------------- |
| G0 Compose-up | PASS    | `docker compose ps` 5/5 healthy; asr endpoint live |
| G1 Type       | PASS    | `pyright` 0 errors                                 |
| G2 Lint       | PASS    | `ruff check .` clean                               |
| G3 Unit       | PASS    | `pytest -q` 266 passed (+32 new)                   |
| G4 Security   | PASS    | see Findings; 10 probes CLEAN                      |
| G5 Cost       | PASS    | see Findings; ASR_TIMEOUT_S=90 matches budget      |
| G6 Spec align | PENDING | _(Evaluator review post-merge)_                    |
| G7 Arch       | PENDING | _(Evaluator review post-merge)_                    |

### security-check Findings

<verbatim paste of the structured Security Findings block>

### cost-check Findings

<verbatim paste of the structured Cost Findings block>

## Test counts

- **Frontend:** 374 tests, 0 new, 0 updated.
- **Backend:** 266 tests, 32 new, 0 updated.

## Playwright UI verification

_(not applicable for this Block — backend-only)_

## Deployment notes

Adds `ASR_BASE_URL`, `ASR_MODEL`, `ASR_TIMEOUT_S` env vars to backend service in `docker-compose.yml`. `requirements.txt` gains `python-multipart`. Rebuild backend image (`docker compose build backend`) before deploy.

## Out-of-scope (carried from SPEC Block)

- Frontend wiring (FE-009)
- Streaming partial transcripts (ADR-0001 §Alternatives, deferred)
- Audio persistence

## Open questions

- _(none)_
```

## Worked example — chore batch (multiple TASKS row flips)

```markdown
## Block

- **Block ID(s):** chore batch — closes BE-014, BE-015, BE-016
- **Block title(s):** post-Block housekeeping (status flips + QA markers)

## Summary

Batches three `chore(tasks):` / `chore(qa):` commits for BE-014/015/016 into a single PR. Each commit on its own is a status-row flip or QA-marker; bundling avoids PR spam per ADR-0005 branch strategy.

## Acceptance (from SPEC Block)

_(N/A — chore batch; the underlying Blocks were closed in their own PRs/commits. This PR only records the lifecycle transitions in TASKS.md.)_

## SPEC and ADR references

- **SPEC:** N/A (TASKS.md flips only)
- **ADRs:** N/A
- **TASKS:** BE-014 / BE-015 / BE-016 → `done`

## Gates passed

| Gate  | Status | Evidence                           |
| ----- | ------ | ---------------------------------- |
| G0–G7 | N/A    | Chore batch — no code/spec changes |

### security-check Findings

_(not applicable for this Block — TASKS.md edits only)_

### cost-check Findings

_(not applicable for this Block)_

## Test counts

- **Frontend:** 396 tests (unchanged).
- **Backend:** 315 tests (unchanged).

## Playwright UI verification

_(not applicable for this Block)_

## Deployment notes

N/A — TASKS.md is documentation; no rebuild required.

## Out-of-scope

- Code changes (those landed in their own PRs)
- SPEC amendments

## Open questions

- _(none)_
```

## How to render and pass to `gh pr create`

```bash
# 1. Construct body in a temp file. Cat-EOF is the simplest path.
cat > /tmp/pr-body-<block-id>.md <<'EOF'
## Block
... (filled body from this skill) ...
EOF

# 2. Sanity-check PHI per security-check Probe 11:
grep -inE '<patterns the project considers PHI tokens>' /tmp/pr-body-<block-id>.md

# 3. Open the PR (per git-pr-flow recipe):
gh pr create \
  --base main \
  --head <branch> \
  --title "$(git log -1 --format=%s)" \
  --body-file /tmp/pr-body-<block-id>.md
```

## Anti-patterns

- Filling the template with bullet copies of the diff. The diff is the diff; the body is why.
- Marking G6/G7 PASS pre-merge. Those are Evaluator-owned and surface after the diff is reviewed.
- Summarising the security-check Findings instead of pasting verbatim. The structured block is the audit trail.
- Adding sections the template doesn't have (e.g. "Why I chose this approach" — that belongs in the commit body).
- Opening a PR with `Open questions` non-empty without `--draft`. A reviewable PR has resolved questions.
- Putting Block IDs in the PR title (`[BE-014] ...`). The title is the conventional-subject; Block IDs live in the body.

## Related documents

- `.github/pull_request_template.md` — GitHub UI auto-fill; this skill is the recipe form.
- `.claude/skills/git-pr-flow/SKILL.md` — the `gh pr create` invocation recipe (companion).
- `AGENTS.md` §8.7 — hard rules on pushing and PRs.
- `AGENTS.md` §8.3 — commit message format (PR title pulls from here).
- `docs/handoff-contract.md` §6 — Refusal triggers (including the `<TBD>` ban).
- `docs/adr/0005-agent-push-and-pr-policy.md` — authorizing ADR.
