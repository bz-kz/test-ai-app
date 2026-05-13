---
name: git-pr-flow
description: Recipe for pushing a Block-class commit to origin and opening a pull request via the gh CLI. Use after a Block's commit-on-self-eval-green step when ADR-0005 is Accepted and the Block warrants its own PR per the branch-strategy matrix below. Hard rules (no push to main, no force-push, no merge) are owned by AGENTS.md §8.7 — this skill is recipe only.
---

# git-pr-flow

**Project rule this skill operates under:** `AGENTS.md` §8 (Commit & branching), specifically §8.2 (Refusals) and §8.7 (Pushing and pull requests). Hard rules live there; this skill is the recipe for executing the permitted operations correctly.

## When to use

- Generator finishes a feature-class Block, runs G0–G3 to green, runs `security-check` / `cost-check` if applicable, and commits per §8.3. The Block warrants its own PR per the matrix in §Branch-strategy decision matrix below.
- Evaluator passes a Block, flips the `TASKS.md` row to `done`, and commits the marker. If the PR is already open (Generator opened it), Evaluator pushes the flip-commit to the same branch and (only when the PR was opened in `--draft`) marks the PR ready.
- Main loop closes a chore / QA batch by pushing the work branch and opening a PR per §Branch-strategy decision matrix.

Do **not** use this skill to:

- Push to `main` (forbidden, AGENTS.md §8.7).
- Merge a PR (forbidden — the human merges).
- Edit a PR body that a different agent or the human opened (forbidden, ADR-0005 §Gates affected).
- Force-push to any branch (forbidden, AGENTS.md §8.7).

## Pre-flight (run in parallel before any `git push`)

These mirror §8.4 pre-commit hygiene; running them again here catches drift between commit-time and push-time (a new file appeared, a hook re-formatted something, the branch fell behind `main`).

```bash
# 1. Confirm working tree is clean and the commit is what you think it is.
git status
git log origin/main..HEAD --oneline

# 2. Confirm the branch is not main and not a protected branch.
git branch --show-current
# If the output is "main" or matches a protected name, STOP and surface to the user.

# 3. Confirm origin points at the expected remote.
git remote -v
# Expect "origin  https://github.com/<owner>/<repo>.git". A different remote is a STOP signal.

# 4. Re-scan staged content for secrets (the same patterns §8.4 names).
# Inspect the diff for `.env`, `*.key`, `*.pem`, `credentials*`, anything under `secrets/`.
git diff origin/main..HEAD --name-only
```

If any of the four returns a STOP signal, do NOT push; surface to the user and stop.

## Push recipe

```bash
# Push the current branch upstream. Set upstream tracking on first push.
git push -u origin "$(git branch --show-current)"
```

Refusals:

- If the push fails because the remote rejected it (typical: branch-protection on `main` if you accidentally pushed there), STOP. Do not retry with `--force`. Surface the error to the user verbatim.
- If the push prompts for credentials, STOP. `gh auth status` should already have set up the credential helper; if it hasn't, hand back to the user.
- `--no-verify` is forbidden (AGENTS.md §8.2). If a pre-push hook fails, fix the underlying issue and re-commit, do not bypass.

## PR creation recipe

```bash
# 1. Verify gh is available and authenticated.
gh auth status
# If this fails, FALL BACK: print a constructed PR URL plus the rendered body to the user, stop.
# Fallback URL shape:
#   https://github.com/<owner>/<repo>/compare/main...<branch>?expand=1
# Render the body and surface both; do not attempt automation beyond surfacing.

# 2. Render the PR body from the template into a temp file.
# The template lives at .github/pull_request_template.md and is rendered by `gh pr create`
# automatically when --body-file is omitted IF gh detects the file. The recipe nonetheless
# materialises the body explicitly so the agent fills the placeholders before push.
cat > /tmp/pr-body.md <<'EOF'
<rendered body — see .github/pull_request_template.md for the schema>
EOF

# 3. Open the PR. Default base is main; default head is the current branch.
gh pr create \
  --base main \
  --head "$(git branch --show-current)" \
  --title "<conventional-prefix>(<scope>): <subject>" \
  --body-file /tmp/pr-body.md
  # Add --draft ONLY when the Block is part of a multi-Block work branch and you intend
  # follow-up commits before review. Otherwise default to --ready (omit the flag).
```

Refusals:

- `--auto-merge`, `--admin`, `--squash`, `--rebase`, `--merge` — forbidden (AGENTS.md §8.7).
- `--base <not-main>` — only with explicit user instruction in the current turn. PRs target `main` by default.
- `--head <branch-that-is-not-current>` — forbidden. The agent pushes and opens a PR for its own branch only.
- Cross-repo / fork PR (`--head <owner>:<branch>`) — forbidden.

## After the PR is open

```bash
# Inspect what the human will see.
gh pr view "$(gh pr list --head $(git branch --show-current) --json number --jq '.[0].number')"
gh pr diff "$(gh pr list --head $(git branch --show-current) --json number --jq '.[0].number')"
gh pr checks "$(gh pr list --head $(git branch --show-current) --json number --jq '.[0].number')"
```

Follow-up commits:

- A QA Failure → fix locally, commit per §8.3 (new commit, never `--amend` after handoff per §8.2), then `git push` again (no PR re-create — the existing PR auto-updates).
- An Evaluator pass → commit the `TASKS.md` flip per §8.3, push to the same branch. If the PR was opened `--draft`, mark it ready: `gh pr ready <number>`. If it was already ready, no extra action — the human merges.

Do **not**:

- Run `gh pr edit --body ...` after the PR has any human comment. Treat human review as the start of conversation — respond with a new commit, not by rewriting the PR body.
- Run `gh pr close` / `gh pr reopen`. The human decides PR lifecycle.

## Branch-strategy decision matrix

Use this matrix to decide whether a Block gets its own branch+PR or batches into a work-branch PR.

| Block class                            | Branch                         | PR timing                                                                                   |
| -------------------------------------- | ------------------------------ | ------------------------------------------------------------------------------------------- |
| `feat:` Block touching ≥3 files        | `feat/<block-id>-<short-slug>` | Open PR on first push; mark `--draft` only if expecting follow-up commits before Evaluator. |
| `refactor:` Block touching ≥3 files    | `refactor/<block-id>-<slug>`   | Same as `feat:`.                                                                            |
| `fix:` Block (bug fix)                 | `fix/<block-id>-<slug>`        | Same as `feat:`.                                                                            |
| `test:` Block (test-only)              | Current work branch is fine.   | Batch into the work-branch PR when it opens.                                                |
| `chore:` / `docs:` Block               | Current work branch is fine.   | Batch.                                                                                      |
| QA-pass marker commit (Evaluator only) | Same branch as the Block.      | Push to existing PR; mark ready if it was draft.                                            |

When in doubt, prefer one PR per Block (single review unit).

Branch-name lint:

- Lowercase, hyphenated, ≤50 chars total.
- Prefix matches conventional-commit type (`feat/`, `fix/`, `refactor/`, `chore/`, `docs/`, `test/`).
- Includes the Block ID (`be-018`, `fe-013`, `inf-004`).
- Includes a short human slug after the Block ID (`be-018-streaming-asr`, not `be-018-changes`).
- Does NOT contain `wip`, `tmp`, `scratch`, or `temp` — those signal the agent isn't ready to push.

## Anti-patterns

- Pushing without re-running the pre-flight checks because "I just committed". The diff between commit-time and push-time is exactly where the user's hook could have re-staged something.
- Opening a PR with `--base 001-ai` because the work branch happens to be `001-ai`. PRs target `main`.
- Opening a PR titled "WIP" or "draft" instead of a conventional-subject title. The title is the lead commit's subject; `--draft` is a flag, not a title hack.
- Filling the PR body's "Gates passed" section by copy-pasting "PASS" with no evidence. Each gate row needs the same evidence (command, observed value, threshold) the Generator already captured at self-eval time.
- Force-pushing the branch to "clean up" history before opening the PR. Force-push is forbidden by §8.7; commit-and-replace is the substitute.
- Treating `gh pr create` failure as a reason to fall back to `git push --tags` or any other side-channel. The fallback is hand-back-to-user, period.
