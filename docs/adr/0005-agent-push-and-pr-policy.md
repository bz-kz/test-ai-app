# ADR 0005: Agents may push feature branches and open PRs; main is human-merge-only

- **Status:** Accepted
- **Date:** 2026-05-13
- **Owner:** Human (operator) — restored after the original record was lost in the PR #1 squash on 2026-05-12
- **Related Spec:** `AGENTS.md` §8.2, `CLAUDE.md` §4

## Context

Original wording in `AGENTS.md` §8.2 was "Never `git push` from any agent. The human pushes." This forced the human to manually transport every agent commit to the remote, which became the bottleneck once the harness produced several commits per session. Meanwhile `main` is now a GitHub-protected branch (configured 2026-05-13), so the risk of an agent accidentally landing changes on `main` is server-side prevented even if a rule slipped.

A prior version of this ADR was authored on branch `001-ai` (commit `cc88e58 chore(planner): ADR-0005 + git-pr-flow skill + PR template`) but did not survive the PR #1 squash-merge into `main`. This file restores the decision so the policy is discoverable from `NOTES.md` and the ADR directory, matching the practice that has been running since.

## Decision

We will allow agents to `git push` to non-default branches and to open PRs via `gh pr create`, while keeping all `main`-touching operations (push to `main`, force-push, PR merge) human-only.

Concretely:

- **Permitted for agents:**
  - `git push -u origin <feature-branch>` where `<feature-branch>` is not `main`.
  - `gh pr create --base main --head <feature-branch>` with a fully populated body per `.github/pull_request_template.md`.
  - Follow-up commits and pushes on the same feature branch.
- **Forbidden for agents (server-side enforced where possible):**
  - `git push origin main` (any form). Blocked by GitHub branch protection.
  - `git push --force` / `--force-with-lease` to `main` or to any branch already pointed at by an open PR ready for review.
  - `gh pr merge` (or clicking Merge in the GitHub UI).
  - Any operation that bypasses required status checks or required reviews on protected branches.

## Consequences

- **Positive:**
  - Removes the human round-trip for the push step. Agent finishes a Block → pushes → opens PR → human only does code review and merge.
  - `main` protection makes the "no agent merge" rule self-enforcing rather than relying on agent discipline alone.
  - Multiple PRs per session become low-friction (this session opened PR #2 / #3 / #4 — would have been three separate hand-offs under the old rule).
- **Negative:**
  - Agents can now silently push partially-broken branches if they skip self-eval gates. Mitigation: `AGENTS.md` §6 still requires G0–G3 green before commit, and CI on GitHub catches the rest.
  - Force-push policy must be very tight to avoid clobbering a parallel reviewer's in-progress comments. Hence the explicit no-force-push wording above.
- **Reversibility:** Cheap. Revert `AGENTS.md` §8.2 to the prior wording and remove this ADR. No code depends on it.

## Alternatives considered

- **Status quo ("human pushes everything").** Rejected — became the throughput bottleneck once sessions produced multiple Blocks per turn (verified during the 2026-05-12 documentation push).
- **Allow agents to merge too (push `main`).** Rejected — `main` protection plus the human-review step are the project's last line of defence; removing them defeats the purpose of having a 3-agent harness with an Evaluator.
- **Permit force-push to feature branches by default.** Rejected — too easy to destroy reviewer-pinned positions on a PR; requires explicit per-turn user instruction.

## Gates affected

- **G7 (Architecture):** None — this is process, not architecture.
- **G6 (Spec alignment):** None directly. The Evaluator should verify the PR body conforms to `.github/pull_request_template.md`.
- **PR-body PHI rule:** PR titles and bodies must obey `.claude/rules/local-llm-and-phi.md` §3 — never embed PHI in PR text. Captured in `security-check` focus area #10 (post-ADR-0005 amendment).

## Open follow-ups

- [x] `AGENTS.md` §8.2 updated to enumerate the new permitted/forbidden matrix and to mention GitHub protection (commit on `005-md-policy-sync`).
- [x] `CLAUDE.md` §4 Git line updated to reference this ADR and the GitHub-protected status of `main` (human-applied edit, same branch).
- [ ] `.claude/agents/generator.md` already references the new push permission (per the 2026-05-12 commit `2cd5945`). Verify the citation still points at `AGENTS.md` §8 after this PR lands.
- [ ] If a `git-pr-flow` skill is reintroduced (it was removed earlier per `AGENTS.md` §8.6), update it to reflect the matrix in this ADR.
