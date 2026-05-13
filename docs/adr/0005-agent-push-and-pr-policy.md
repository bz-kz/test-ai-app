<<<<<<< 005-md-policy-sync
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
=======
# ADR 0005: Agents may push to non-default branches and open PRs (no merge)

- **Status:** Accepted
- **Date:** 2026-05-12
- **Owner:** Planner (Claude Opus 4.7)
- **Related Spec:** `AGENTS.md` §8 (Commit & branching), `.claude/rules/local-llm-and-phi.md` §6 (verification commands the user wants run pre-push)

## Context

`AGENTS.md` §8.2 currently says "Never `git push` from any agent. The human pushes." This was the right default while the repo lived purely on the user's laptop. As of 2026-05-12 the project has a GitHub remote (`origin → https://github.com/bz-kz/test-ai-app.git`) and the user wants agent work to surface as **pull requests** rather than as local commits the user re-pushes by hand. The clinician-style review loop the project already runs (Generator → Evaluator on `TASKS.md`) maps cleanly onto a PR review loop; the missing piece is permission to push the work branch and open the PR.

Three forcing functions surface together:

1. **Friction of manual push.** Every closed Block currently ends with the user typing `git push origin <branch>` themselves. The agent already produces a structured commit (subject, body, `Co-Authored-By`) — the PR body is the logical extension of the same information and would let the user review via GitHub's diff/file-comment UI rather than `git log -p`.
2. **Asymmetry between commit and push.** §8.2 forbids `git push` outright but §8.3–§8.5 invest heavily in commit-message and commit-content discipline. The implicit assumption is that commits are reviewable; on a multi-Block branch they pile up faster than `git log` reading scales. PRs are the unit at which GitHub's review UI works.
3. **Risk of accidental scope creep.** Lifting the push prohibition without naming the boundaries (which branches, which commands, who merges) would re-create the very ambiguity §8 was written to close. Specifically: pushing to `main`, force-pushing, `--auto-merge`, branch deletion on the remote, and history rewrites are all qualitatively different from "open a PR". A single ADR is the cleanest way to draw the new line.

Without an ADR, the change would touch `AGENTS.md` §8 (cross-agent contract — protected by the new convention of agents proposing candidate text the human applies), introduce a new skill recipe for PR creation, and ripple into Evaluator's commit-on-pass step (`TASKS.md` row → `done`). A binding decision record names the boundary all three pieces share.

## Decision

We will permit every agent to **push to non-default, non-protected branches and open a pull request via `gh pr create`** at the end of a Block's commit-on-self-eval-green step, while preserving the existing prohibitions on pushing to `main`, force-pushing, and any form of merge (auto- or manual). Pull-request merge remains the human's sole responsibility.

Concretely:

- **Permitted operations (agents):**
  - `git push origin <branch>` where `<branch>` is **not** `main` and **not** any branch flagged as the default / protected branch on GitHub.
  - `gh pr create --base main --head <branch> --title "<conventional-subject>" --body "<templated-body>" --draft|--ready` (defaults to `--ready`; `--draft` is opt-in when the Block is incomplete on a multi-Block work branch).
  - `gh pr view <number>`, `gh pr diff <number>`, `gh pr checks <number>` — read-only inspection of in-flight PRs the agent has opened.

- **Forbidden operations (agents):**
  - `git push origin main` (any form).
  - `git push --force` / `--force-with-lease` on any branch, including the agent's own feature branch. History rewrite remains human-only.
  - `gh pr merge`, `gh pr merge --auto`, `gh pr merge --admin`, `gh pr merge --squash|--rebase|--merge` — the human merges. Auto-merge is forbidden even when CI would gate it.
  - `gh pr close`, `gh pr reopen` (the human decides PR lifecycle).
  - `git push --delete origin <branch>` (remote branch deletion is human-only).
  - `gh pr edit` after the PR is open and a human has commented (treat human comments as a refusal-style signal; respond with a new commit, not an edit of the PR body).
  - Any `--no-verify` or hook bypass during push (mirrors §8.2's commit rule).
  - Cross-repo / fork pushes. The agent pushes to `origin` only.

- **Branch strategy (recommended):** A new feature-Block branch is cut off `main` for any Block whose surface is mostly new code (`feat:` / sizeable `refactor:`). The branch name is `<conventional-prefix>/<block-id>-<short-slug>`, e.g. `feat/be-018-streaming-asr`. Chore / QA-pass / `docs:` commits land on the current work branch (today `001-ai`) and are batched into a single PR when the work branch is ready for review. The detailed decision matrix lives in §Open follow-ups so it can evolve without re-issuing this ADR.

- **PR-title and PR-body conventions:** The PR title MUST match the lead commit's conventional-subject form (`<prefix>(<scope>): <subject>`, ≤72 chars). The PR body MUST follow the template in `.github/pull_request_template.md` (created as a separate file by this ADR's hand-off), which carries: Block ID, Acceptance bullets ticked, SPEC/ADR references, gates passed, embedded `security-check` and `cost-check` Findings when the Block is PHI- or inference-touching, test counts, and a deployment-notes line (typically `N/A — local PoC`). The `Co-Authored-By` trailer that the commit already carries is sufficient; no additional "generated with" footer is required on the PR body itself.

- **gh CLI fallback:** If `gh` is unavailable or not authenticated in the local environment, the agent MUST surface a constructed PR URL plus the rendered Markdown body to the user and stop — no automation. The fallback is **not** a degraded automatic mode (e.g. opening the URL via `open`); it is a hand-back to the human.

- **Co-existence with `AGENTS.md` §8:** §8.2's prohibitions on `--amend` after handoff, `--no-verify`, destructive ops, `git add -A`, editing human-only files, `git log -uall`, and the §8.4 pre-commit hygiene checklist remain unchanged. This ADR adds two new lines under §8.2's "non-negotiable" header (the proposed wording is in the handoff envelope this ADR ships with). The pre-commit hygiene block in §8.4 is extended with a **pre-push checklist** mirroring the pre-commit one: `git status` (clean), `git log origin/main..HEAD --oneline` (matches stated intent), branch-name lint (not `main`, not a protected branch).

This is a single decision because the five parts (push permission, PR creation permission, branch-strategy default, PR template, gh-CLI fallback) cannot land independently without re-creating the ambiguity §8 was written to close.
>>>>>>> main

## Consequences

- **Positive:**
<<<<<<< 005-md-policy-sync
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
=======
  - The user receives PRs they can review in GitHub's diff/file-comment UI instead of `git log -p` on a local branch. Comment-replies on a PR map naturally to follow-up Generator commits on the same branch.
  - The agent's existing commit discipline (subject style, `Co-Authored-By`, gate evidence) extends naturally into PR-body content; no new artefact discipline is invented.
  - The `main` branch remains the single source of truth for "human-reviewed and merged" state. Default-branch protection (configured on the GitHub side by the human) is the technical enforcement of this ADR's "no push to main" clause.
  - Per-Block PR branches keep the diff scope small enough for the Evaluator-style review loop to remain meaningful at GitHub-scale (a 30-file PR is reviewable; a 30-Block batch is not).
- **Negative:**
  - The agent now has remote-side capability it didn't have before; mis-targeting (pushing to `main`, opening a PR with the wrong base) is a class of error the prior rule eliminated by construction. Mitigated by: explicit branch-name lint, explicit `gh pr create --base main --head <branch>` (never just `gh pr create`), and the pre-push checklist.
  - GitHub Actions / CI minutes are now consumed on every PR open and push (if CI is configured). The project today has no CI configured; if it is added later (see §Open follow-ups), agents will create CI load and the user should weigh the budget. For now, zero cost.
  - The PR-body template duplicates content already in the commit body. This is intentional (PR-body is the artefact the human sees in the GitHub UI); the cost is small.
  - `gh` is an additional local dependency the user must install and authenticate. The fallback (surface URL + body to user) mitigates the dependency at the cost of one extra manual step when `gh` is missing.
- **Reversibility:** Cheap. Reverting requires a superseding ADR that re-tightens §8.2 to "Never `git push`" and removes the new skill recipe. No code depends on this ADR's shape; the change is process-only.

## Alternatives considered

- **Keep §8 strict, automate push via a one-shot user-side script (e.g. `make ship-block`):** rejected — the user explicitly asked for the PR review loop, which a local script cannot provide. The script would also re-implement what `gh pr create` already does, at a maintenance cost.
- **Allow `gh pr merge` for chore-class Blocks:** rejected — merge is the moment human review becomes binding. Allowing auto-merge for "small" classes creates an exception ladder ("`docs:` is auto-mergeable, `chore:` too, why not `test:`?") with no defensible stopping point. Mirrors the LLM rule's "no hosted SDKs even for small calls" stance.
- **Long-lived work branch (`001-ai`) → one batched PR to `main` containing the entire 150-commit history:** rejected as the steady-state default — a 150-commit PR exceeds GitHub's reviewable-diff scale, and per-Block branching gives the user a meaningful review unit. Accepted as a one-time transitional step (see §Open follow-ups): user pushes `main` once to seed the default branch, then per-Block branching going forward; the existing `001-ai` history converges into `main` only via small PRs, never as a single mega-PR.
- **Per-Block branches off `001-ai` instead of off `main`:** rejected — a per-Block branch should target the branch it will merge into, and `main` is the merge target. Branching off a long-lived intermediate branch creates rebase-debt every time `main` advances independently. The `001-ai` branch can remain as a parking spot for in-flight chore commits, but feature-Block branches cut off `main`.
- **Skip the PR-body template; let the commit body suffice:** rejected — the PR body is the artefact the human reviews in GitHub's UI. The commit body is visible only one click in. A small template duplication earns a meaningful UX improvement.
- **Reintroduce `.claude/skills/git-operations/SKILL.md` and put the PR recipe inside it:** rejected — `AGENTS.md` §8.6 explicitly says reintroducing a git-specific Skill requires an ADR because the inline rules are load-bearing. This ADR introduces a **separate** skill `.claude/skills/git-pr-flow/SKILL.md` scoped narrowly to the PR recipe (not "git operations" generally), which keeps the inline §8 rules canonical and adds only the PR-creation recipe alongside them. The skill is recipe-only; hard rules stay in §8.
- **Allow `--force-with-lease` on agent feature branches (e.g. to rebase before re-push):** rejected for v1 — history rewrite is a class of operation the agent gets wrong silently. If the human needs the branch rebased onto `main`, the human runs it. Revisit if rebase friction becomes a real complaint with evidence (file a follow-up ADR).
- **Use a hosted GitHub App / bot identity to open the PR instead of the agent's local credentials:** rejected for the local-only PoC scope — installing a GitHub App, scoping its permissions, and rotating its token is more operational surface than the project needs. `gh` under the user's own credentials is the lowest-friction path. If the project ever ships beyond local-PoC, revisit.

## Gates affected

- **G0 (Compose-up):** unaffected. PR creation is repo-side; compose is unchanged.
- **G4 (Security / PHI):** **unchanged in shape**, but `security-check` gains an additional informational probe: scan the staged diff and the PR body for unmasked PHI before push. The probe is informational (WARNING-class, not auto-fail) because PHI in a commit message would already have failed §8.4's `git diff --cached` check; the PR-body probe catches the case where the human-readable template was filled out with raw values rather than masked references. The new probe wording goes into `.claude/skills/security-check/SKILL.md` (proposed text in the handoff envelope).
- **G5 (Cost / Inference budget):** unaffected. PR creation has no inference impact.
- **G6 (Spec alignment):** Evaluator's commit-on-pass step (today: flip `TASKS.md` row to `done`, commit, stop) gains a continuation: after the flip-commit, the Evaluator MAY push the same branch and call `gh pr ready` (if the PR was opened in `--draft`) or update the PR body's Acceptance checklist via `gh pr edit` if and only if the PR was opened by the **same** agent in the **same** session — never edit a PR a different agent or the human created. This is the only edit-PR-body permission granted, and it is scoped to "tick the box that this Evaluator just verified".
- **G7 (Architecture):** unaffected. PR-flow is a process gate, not an architectural one.

## Open follow-ups

- [ ] Human edits `AGENTS.md` §8.2 per the proposed text in this ADR's handoff envelope (agents cannot edit `AGENTS.md` per the convention saved 2026-05-12). The edit ADDs two clauses to §8.2's "Refusals (non-negotiable)" list (push to `main`, force-push) and ADDs a new sub-section §8.7 "Pushing and pull requests" with the permitted/forbidden matrix.
- [ ] Human extends §8.4 pre-commit hygiene to add the pre-push checklist (proposed text in handoff envelope).
- [ ] Human flips this ADR's Status from `Proposed` to `Accepted` once the wording is settled.
- [ ] Human pushes `main` once to seed the GitHub default branch (the remote currently has no `main` until the first push lands). After this one-time seeding, agent-opened PRs target `main` as base.
- [ ] Human configures branch-protection rules on `main` (require PR, disallow force-push, require linear history if desired). The agent rules above are belt; GitHub branch-protection is suspenders. Both should exist.
- [ ] Generator implements `.claude/skills/git-pr-flow/SKILL.md` (created by this ADR's handoff to capture the PR recipe). The skill is a recipe, not new policy; policy lives in §8 and in this ADR.
- [ ] Generator implements `.github/pull_request_template.md` (created by this ADR's handoff). The template is referenced by the skill recipe and rendered by `gh pr create --body-file ...`.
- [ ] Add a follow-up Block (out of scope for this ADR) for GitHub Actions running G1/G2/G3 on PR open/update. CI integration is orthogonal to PR-creation permission; it can land later when the user wants the gates to run on the remote rather than only locally. The PR template's "Gates passed" section should be filled in by the Generator pre-push regardless of CI.
- [ ] Re-evaluate after the first ~5 agent-opened PRs land. If branch naming, PR-body field order, or the gh-CLI fallback show real friction, file a follow-up ADR adjusting the convention with evidence.
- [ ] If `gh` becomes unavailable on the user's machine more than once, evaluate whether the fallback (surface URL + body) is enough or whether the user wants the agent to use `git push` only and skip the PR-creation step entirely. The current ADR treats `gh` as the default path and the URL-fallback as the exception.
>>>>>>> main
