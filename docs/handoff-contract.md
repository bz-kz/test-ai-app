# Handoff Contract

Single source of truth for the structured blocks that flow between Planner, Generator, and Evaluator. Every `SPEC.md`, every `TASKS.md` entry, and every agent-to-agent prompt MUST conform to this schema. Sub-agents that receive a block not matching this schema MUST refuse and request reformatting.

## 1. Why this exists

The 3-agent harness (Planner / Generator / Evaluator) only works if all three read and emit the same shape. Free-form prose creates misreads, looping, and silent drift. A fixed shape lets each agent verify completeness mechanically before acting.

## 2. The Block

Every Spec section, Task entry, and inter-agent prompt is a **Block** with these fields. Required fields MUST be present even if empty (write `_(none)_`).

```
## <Block Title>                      # Required. Human-readable, scope-narrow.

- **Goal:** <1–2 sentences>           # Required. The outcome, not the steps.
- **Inputs:**                          # Required. Existing artifacts to read.
  - <path>#<section> — <why>
- **Acceptance:**                      # Required. Checklist of verifiable criteria.
  - [ ] <criterion>
- **Out-of-scope:**                    # Required. What this Block will NOT do.
  - <bullet>
- **Open-questions:**                  # Required. Empty = `_(none)_`.
  - <bullet>

# Optional fields — include only when relevant:
- **Inference Impact:** <yes|no>; <prompt strategy>; <approx token length>
- **Data Sensitivity:** <none|PII|PHI>; <handling notes>
- **Gates Touched:** G0, G1, …        # Which DoD gates this Block must clear.
- **Affected Layers:** domain | usecases | infrastructure | interfaces | atoms | molecules | organisms
```

### 2.1 Field rules

- **Goal** describes the _result_, not the implementation path. Implementation lives in the Generator's task list, not the Spec.
- **Inputs** MUST point at concrete artifacts (file path + section anchor) or external references with stable URLs. Absent inputs = Planner failure.
- **Acceptance** items MUST be testable: a command, a visible behaviour, or a measurable threshold. Subjective adjectives ("clean", "intuitive") MUST be replaced with the gate they map to (e.g. `G7 Architecture`, `G6 Spec align`).
- **Out-of-scope** is non-optional. An empty Out-of-scope list is a smell — Planner SHOULD push back at least one item to anchor the boundary.
- **Open-questions** unresolved at handoff stop the next agent. Generator MUST NOT silently choose; it returns the Block to Planner.

## 3. Inter-agent prompt envelope

When agent A hands off to agent B, the prompt body is one or more Blocks plus a thin envelope:

```
# Handoff: <from> → <to>

**Reason:** <why we are handing off now>
**Reference SPEC:** <path>#<section>
**Reference TASKS:** <path>#<task-id>

---

<one or more Blocks here>
```

The envelope's three lines plus the Block(s) are the entire prompt. No additional prose.

## 4. Failure response shape (Evaluator → Generator)

When the Evaluator fails work, it returns a Block with this title and required fields:

```
## QA Failure: <task-id>

- **Goal:** Surface every gate that did not pass so Generator can fix without re-discovery.
- **Inputs:**
  - <task-id> — last submitted state
- **Acceptance:**
  - [ ] All gates listed below pass on re-run.
- **Out-of-scope:** New scope changes (escalate to Planner instead).
- **Open-questions:** _(none)_
- **Gates Failed:**
  - **G<n> <name>:** <observed> vs <threshold>; reproduction: `<command>`
- **Suggested first fix:** <one sentence; non-binding>
```

`Suggested first fix` is advisory. Generator owns the implementation choice.

## 5. Escalation shape (Evaluator → Planner)

When repeated failures indicate the spec itself is wrong:

```
## Spec Pivot Request: <task-id>

- **Goal:** Re-anchor the Spec because the current design cannot satisfy the gates.
- **Inputs:** <task-id>, <previous QA failure block>
- **Acceptance:**
  - [ ] Updated Spec block(s) committed.
  - [ ] New handoff to Generator is issued.
- **Out-of-scope:** Implementation changes.
- **Open-questions:** <list of unknowns Planner must resolve>
- **Evidence:** <2–3 bullets summarising why iteration is exhausted>
```

## 6. Refusal rules

A receiving agent MUST refuse and bounce a handoff back when ANY of:

1. A required field is missing or contains a placeholder like `TBD`, `?`, `…`.
2. Acceptance contains non-testable items.
3. `Open-questions` is non-empty (Planner must close them first).
4. The Block touches PHI but `Data Sensitivity` is unset.
5. The Block touches inference but `Inference Impact` is unset.

Refusal response shape:

```
## Handoff Refused: <task-id>

- **Goal:** Return this Block to <sender> for repair before any work begins.
- **Inputs:** <original handoff>
- **Acceptance:**
  - [ ] Listed defects are fixed.
- **Out-of-scope:** Doing the work.
- **Open-questions:** _(none)_
- **Defects:**
  - <field> — <what is wrong>
```

## 7. Minimum viable example

```
## Patient Search by MRN

- **Goal:** Allow a clinician to find a patient record by Medical Record Number from the records list.
- **Inputs:**
  - SPEC.md#patient-record — domain model
  - DESIGN.md#inputs — input field spec
  - DESIGN.md#ai-output-patterns — n/a, AI not used here
- **Acceptance:**
  - [ ] GET /patients?mrn=<value> returns 200 with one record on hit, 404 on miss.
  - [ ] Frontend list filters within 200 ms for ≤10k local rows.
  - [ ] No PHI is written to console or log on miss.
- **Out-of-scope:** Fuzzy matching; cross-tenant search; audit log.
- **Open-questions:** _(none)_
- **Inference Impact:** no
- **Data Sensitivity:** PHI; logs MUST mask MRN in any error path.
- **Gates Touched:** G1, G2, G3, G4, G6
- **Affected Layers:** domain, usecases, interfaces, molecules
```

## 8. Versioning

Changes to this contract MUST be recorded as an ADR in `docs/adr/`. Agents read this file at the start of every session; a contract change without an ADR is a process violation.
