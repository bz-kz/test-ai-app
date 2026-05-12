# ADR 0004: PHI buffers MUST live in `useRef`, not `useState`

- **Status:** Proposed
- **Date:** 2026-05-12
- **Owner:** Generator (main loop) — drafted post-FE-013 first QA Failure
- **Related Spec:** `.claude/rules/local-llm-and-phi.md` §4, `frontend/SPEC.md#voice-capture`, `frontend/SPEC.md#streaming-voice-capture`

## Context

FE-013's first QA submission (commit `0173b60`) stored the assembled chunked transcript text in `useState<StreamingInfo>.partialText`. The SPEC §voice-capture line 119 already required "partial transcript lives in `useRef` only (no React state for chunked text bodies that DevTools would snapshot)" but this was not explicit in the project-wide PHI rule `local-llm-and-phi.md`. The QA Evaluator (agent `a5c4d69a3086f5b29`) correctly flagged the violation; commit `fd751d4` resolved it by deriving `partialText` from a `useRef` at the hook return-shape construction site.

The forcing function is **React DevTools' Hooks Inspector**: it captures every `useState` value in real time, allowing an attacker (or accidental observer) to read accumulated PHI from a developer machine even when the actual rendered DOM never displayed it persistently. `useRef` values are NOT captured in the same way — refs are intentionally outside React's reconciliation snapshot.

The rule clause currently in `local-llm-and-phi.md` §4 says "Memory only" but doesn't distinguish `useState` from `useRef`. This ADR proposes a clarifying clause so future agents (including future Planner sessions) cannot interpret "memory" loosely.

## Decision

Extend `.claude/rules/local-llm-and-phi.md` §4 with the following binding clauses:

1. **PHI-bearing buffers and accumulators MUST live in `useRef` (or equivalent stable, non-snapshot storage).** Examples: audio Blob, chunked partial transcripts, accumulated SSE chunks before completion, streaming-draft buffer before final `setDraft`.
2. **Counters, status flags, and structural metadata MAY live in `useState`** because they contain no PHI: `chunkIndex: number`, `chunkCount: number | null`, `status: "uploading" | "success" | ...`, `elapsedMs: number`.
3. When a component needs to display the buffered content (the typical case — the molecule shows partial text during streaming), the rendered string MUST be **derived at render time** from the `useRef` content. A common pattern: `useState<number>` tick counter that is incremented per chunk arrival to force a re-render; the molecule reads `ref.current.join("")` on every render and consumes the result.
4. The rule applies symmetrically on the **backend** side for any in-process buffer (e.g. a streaming generator's accumulator). PHI bytes / text MUST not be added to long-lived dataclasses or attribute slots accessible via repr/str; use locally-scoped `list[str]` or `bytearray` inside the function scope and explicitly drop the reference when the stream completes.

## Consequences

- **Positive:**
  - Future Generators implementing streaming-PHI features cannot pass G4 review by placing accumulators in `useState` even if the rendered DOM appears safe.
  - The `security-check` skill's Probe 10 can extend to grep for `useState<.*partialText|useState<string\\[\\]>` patterns in voice / streaming files as an additional check (follow-up; not required for this ADR's acceptance).
  - The existing FE-013 implementation (`fd751d4`) is already compliant — no migration burden.
- **Negative:**
  - Slightly more boilerplate when implementing streaming UIs (tick counter + derived string vs single `useState<{...}>` blob).
  - Developer mental model adjustment: "PHI ≠ React state, even briefly".
- **Reversibility:** Easy. Reverting requires a superseding ADR; the clause additions are textual and don't depend on any code structure.

## Alternatives considered

- **Leave the rule as `Memory only` (status quo).** Rejected — FE-013 demonstrated the ambiguity-driven failure mode. The QA cycle caught it but at the cost of one fix-up commit; a stricter rule would have shifted the catch to Generator self-eval.
- **Add the clause to `frontend/SPEC.md` only.** Rejected — backend has the same conceptual surface (PHI buffers in long-lived structs). A project-wide rule is cleaner.
- **Auto-lint via ESLint custom rule.** Rejected as v1 — the cost of writing a TypeScript AST rule that distinguishes "PHI buffer" from "non-PHI buffer" exceeds the value. Manual grep + reviewer judgment is sufficient at PoC scale.

## Gates affected

- **G4 (Security / PHI):** `security-check` skill Probe 10 wording updated to mention this clause explicitly (follow-up in §Open follow-ups below). No change to the existing 10-probe matrix.
- **G6 (Spec alignment):** Evaluator now has an explicit clause to cite when flagging `useState<...PHI...>` patterns. Previously the only source was the SPEC block, which not every Block referenced.

## Open follow-ups

- [ ] Human edits `.claude/rules/local-llm-and-phi.md` §4 per this ADR's §Decision (agents cannot edit `.claude/rules/` per `AGENTS.md` §3).
- [ ] Update `.claude/skills/security-check/SKILL.md` Probe 10 wording to enumerate the `useState<...>` anti-patterns for PHI buffers.
- [ ] Update `frontend/SPEC.md#voice-capture` to reference this ADR rather than restating the rule inline.
- [ ] Consider whether `backend/SPEC.md` needs a parallel clause for backend buffer hygiene (low priority — backend code paths are short-lived per request).
