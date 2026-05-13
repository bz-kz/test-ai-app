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
| `/CLAUDE.md` (project root)                      | Human only          | Project-wide policy file; agents propose text, never edit (2026-05-12).          |
| `~/.claude/CLAUDE.md` (user global)              | Human only          | User's cross-project preferences; agents propose text only (2026-05-12).         |
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

### 8.1 When and what to commit

- One feature Block ≈ one commit. The commit subject names the Block ("Patient search by MRN" → `feat: patient search by MRN`).
- Generator commits after self-eval is green and BEFORE invoking Evaluator. Evaluator commits a tag/marker on pass; on fail, the Generator's commit stays as the work-in-progress record.
- Never commit unless the user asked for a commit in the current turn (Generator's self-eval-green is the trigger for _its_ Block commits; for ad-hoc edits, wait for the user).

### 8.2 Refusals (non-negotiable)

<<<<<<< 005-md-policy-sync
- Never `git push origin main` (any form). `main` is a GitHub-protected branch (configured 2026-05-13); the rule is enforced both by agent discipline and server-side. Force-push to `main` is likewise blocked. Pushing to non-default feature branches and opening PRs via `gh pr create` is permitted (the human merges).
=======
- Never `git push origin main` (any form). Never push to a branch flagged as the default / protected branch on GitHub. Pushing to other branches is permitted per §8.7.
- Never `git push --force` / `--force-with-lease` on any branch, including the agent's own feature branch. History rewrite remains human-only.
>>>>>>> main
- Never `--amend` a commit that has been handed to the Evaluator. Add a follow-up commit instead.
- Never `--no-verify` / `--no-gpg-sign` or any hook bypass. If a hook fails, fix the underlying issue and create a new commit.
- Never destructive ops (`reset --hard`, `clean -fd`, `branch -D`, `checkout -- <path>`, `restore <path>`, `push -f`, `rebase -i`) without an explicit user instruction in the current turn.
- Never `git add -A` / `git add .`. Stage by explicit path so secrets and large binaries can't slip in.
- Never edit human-only files via git tooling (see §3: `.claude/settings.json`, `.claude/agents/*.md`, `.claude/rules/*.md`).
- Never `git log -uall` (memory-exhaustive on large repos).
<<<<<<< 005-md-policy-sync
- The PR _merge_ remains human-only. Agents never call `gh pr merge` or click the GitHub merge UI; they hand the PR off and stop.
=======
- Never `gh pr merge` in any form (`--auto`, `--admin`, `--squash`, `--rebase`, `--merge`). Never `gh pr close` / `gh pr reopen` / `git push --delete`. Merge is the human's sole responsibility. See §8.7 for full PR-flow rules.
>>>>>>> main

### 8.3 Commit message format

- English, imperative, ≤72-char subject.
- Conventional prefix: `feat:` `fix:` `refactor:` `test:` `docs:` `chore:`. Use a scope when it adds clarity: `feat(backend): ...`, `fix(frontend): ...`.
- Body only when the _why_ is not obvious from the diff.
- HEREDOC form with a single-quoted delimiter, ending in a `Co-Authored-By:` trailer (model name reflects who composed the commit — e.g. `Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>`):

  ```bash
  git commit -m "$(cat <<'EOF'
  <subject>

  <optional body>

  Co-Authored-By: Claude <model> <noreply@anthropic.com>
  EOF
  )"
  ```

### 8.4 Pre-commit hygiene

Before every `git commit`, run in parallel:

1. `git status` — confirm the staged set matches stated intent.
2. `git diff --cached` — confirm the staged content is what was described.
3. `git log --oneline -n 5` — match the repo's existing subject style.

Scan staged paths for `.env*`, `*.key`, `*.pem`, `credentials*`, anything under `secrets/`. Any match → STOP, surface to the user, do not commit even if the user said "commit everything".

Before every `git push`, run in parallel:

1. `git status` — working tree clean.
2. `git log origin/main..HEAD --oneline` — the commits about to be pushed match stated intent.
3. `git branch --show-current` — confirm the branch is NOT `main` and NOT a default / protected branch.
4. `git remote -v` — confirm `origin` points at the expected GitHub URL; a different remote is a STOP signal.

If any check returns a STOP signal, do NOT push; surface to the user.

### 8.5 Hook-failure protocol

If `git commit` fails due to a pre-commit hook:

1. The commit did **not** happen — `--amend` would touch the _previous_ commit. Do not amend.
2. Read the hook output, fix the underlying issue (lint / type / format / test).
3. `git add -- <fixed paths>` and re-run the same HEREDOC commit as a **new** commit.

### 8.6 Why these rules are inline (not in a Skill)

Earlier the project had a `git-operations` Skill that codified the same rules; it was removed once the rules proved load-bearing enough to live in the cross-agent contract directly. Reintroducing a git-specific Skill requires an ADR — agents should not re-skillify what is already canonical here. The `.claude/skills/git-pr-flow/SKILL.md` and `.claude/skills/pr-body-template/SKILL.md` (ADR-0005 authorized) are recipe-only; hard rules stay in §8.

### 8.7 Pushing and pull requests

Permitted (per ADR-0005):

- `git push origin <branch>` where `<branch>` is NOT `main` and NOT a default / protected branch.
- `gh pr create --base main --head <branch> --title "<conventional-subject>" --body-file <rendered>`. Defaults to `--ready`. Use `--draft` only when the Block is part of a multi-Block work branch and follow-up commits are expected before review.
- `gh pr view <n>`, `gh pr diff <n>`, `gh pr checks <n>` — read-only inspection of agent-opened PRs.
- `gh pr ready <n>` — only on a PR THIS agent opened in THIS session, only when flipping from `--draft` to ready, only as the Evaluator's commit-on-pass continuation.

Forbidden (mirrors §8.2 additions):

- Push to `main`. Force-push to anything. Remote branch deletion (`git push --delete`).
- Any form of merge (`gh pr merge` with any flag). The human merges.
- `gh pr close` / `gh pr reopen`. The human decides PR lifecycle.
- `gh pr edit` after the PR has any human comment. Respond with a new commit, not a body rewrite.
- Cross-repo / fork pushes. Origin only.
- `--no-verify` / `--no-gpg-sign` during push (mirrors §8.2's commit rule).

Recipe lives in `.claude/skills/git-pr-flow/SKILL.md`. PR body template lives in `.claude/skills/pr-body-template/SKILL.md` (skill form) and `.github/pull_request_template.md` (GitHub auto-fill). Hard rules above are canonical; the skills are recipe-only.

Branch strategy default: feature-class Blocks (`feat:`, `refactor:`, `fix:` ≥3 files) get `<prefix>/<block-id>-<short-slug>` cut off `main` with a per-Block PR. Chore / docs / test Blocks batch onto the current work branch (`001-ai`-style) and PR when the branch is ready for review. Full matrix in the skill recipe.

`gh` unavailable → fall back to surfacing the constructed PR URL and rendered body to the user; do NOT automate around a missing `gh`.

## 9. Things every agent should keep visible

- Latency budget and PHI rule are the two cliffs everyone falls off first; check both before declaring Done.
- An empty `Out-of-scope` field is almost always a sign the Block has not been thought through.
- A change that touches `docker-compose.yml` re-arms G0; Generator MUST re-run it.
- An ADR is cheap. Use one whenever a decision will outlast the current task.
