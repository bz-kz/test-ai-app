# Rule: Architecture Layer Direction

This rule is binding. It centralizes layer-direction enforcement that was previously scattered across `CLAUDE.md` §5, `backend/SPEC.md#layer-boundaries`, and `frontend/SPEC.md#layer-rules`. Violations are CRITICAL G7 findings and block QA Pass.

## 1. Backend (FastAPI + DDD)

Direction is **inwards only** — layers MUST import strictly toward the centre:

```
interfaces ──→ usecases ──→ infrastructure ──→ domain
   ↑                                              │
   └── usecases re-exports                        │
                                                  │
domain ──────────────────────────────────────────┘
   (domain imports nothing — pure)
```

Binding clauses:

1. **`app/domain/` MUST NOT import** from `app/usecases/`, `app/infrastructure/`, or `app/interfaces/`. Domain is dependency-free except for `__future__` and stdlib.
2. **`app/usecases/` MUST NOT import** from `app/interfaces/` (no FastAPI / Pydantic Request models).
3. **`app/interfaces/` (routers) MUST NOT import directly** from `app/infrastructure/`. Cross via `app/usecases/di.py` re-exports (the established BE-006 / BE-014 / BE-017 seam).
4. **`app/usecases/` is the only layer that constructs/invokes** `LocalLLMClient` / `LocalASRClient` / repository instances.
5. Direct `httpx.post(...)` / `requests.post(...)` / `fetch(...)` to `http://llm:...` or `http://asr:...` outside `app/infrastructure/llm/` or `app/infrastructure/asr/` is a G7 failure even if functionally correct. (Also a §1 violation of `local-llm-and-phi.md`.)
6. **Errors re-export pattern** (`app/usecases/errors.py` re-exports `InferenceError`, `ASRError`): pre-existing BE-014 precedent; allows routers to consume the typed exception without breaking layer direction. Do NOT introduce additional `__init__.py` re-exports that bypass this seam.

## 2. Frontend (Next.js + Atomic Design + Onion)

Direction is **outwards only** — pages assemble; atoms know nothing:

```
pages (app/) ──→ hooks ──→ services ──→ fetch
                              │
                              └── lib/api.ts (apiFetch) or raw fetch (multipart/SSE only)

components:
  atoms ←── molecules ←── organisms     (upward dependency only)
  atoms know nothing about services / hooks
```

Binding clauses:

1. **No `fetch(` in components or `app/` pages.** All HTTP lives in `src/services/`. Exception: a service file MAY use raw `fetch` directly when `apiFetch` is insufficient (multipart upload, SSE consumer) — document the exception with a one-line header comment. Currently exempt: `services/transcribe.ts`, `services/drafts.ts` (streamRecordDraft).
2. **No `fetch(` / `XMLHttpRequest` / `EventSource` in atoms.** Atoms are presentational. The atom may receive callbacks via props; the callback owner is the molecule / hook / page.
3. **Molecules import** atoms + hooks + constants + types. Molecules MUST NOT import services directly — go through hooks.
4. **Organisms** are higher-level molecules with multiple sub-molecules. Same import rules as molecules.
5. **Pages (`app/`)** import organisms / molecules / hooks. Pages MAY import services for non-stateful one-shot calls, but the hook pattern is preferred.
6. **No PHI in `console.log` / `console.warn` / `console.error`.** Apply `maskPhi(...)` if you must debug. Verified by `.claude/skills/security-check/SKILL.md` Probe 9.
7. **No PHI in `localStorage` / `sessionStorage` / `IndexedDB` / URL search params.** Audio Blob, ASR transcript, draft content, encounter UUID belong in component / hook state — and for buffers, in `useRef` (see `local-llm-and-phi.md` §4 erratum).
8. **Infrastructure mounts (`src/components/_<name>/`)** are a fourth class alongside atoms / molecules / organisms. They are 
`_`-prefixed (Next.js convention で route 化されない) client islands that mount once from layout for SDK init or similar 
side-effect-only purpose。DOM を持たず null を return する。現状の唯一の例は `_rum/RumInit.tsx` (ADR-0006 FE-015)。新規追加には ADR
必須。


## 3. Verification commands

These run as part of the `security-check` skill probe matrix but are also valid standalone:

```bash
# Backend layer direction
grep -RnE '^from app\.usecases|^from app\.infrastructure|^from app\.interfaces' backend/app/domain/ && exit 1 || echo "domain clean"
grep -RnE '^from app\.interfaces' backend/app/usecases/ && exit 1 || echo "usecases→interfaces clean"
grep -RnE '^from app\.infrastructure' backend/app/interfaces/ | grep -v 'errors' && exit 1 || echo "interfaces→infra clean (errors re-export OK)"

# Backend inference / ASR direct calls
grep -RnE 'http://llm[: ]|ollama' backend/app | grep -v '^backend/app/infrastructure/llm/' && exit 1 || echo "no LLM bypass"
grep -RnE 'http://asr[: ]|whisper' backend/app | grep -v '^backend/app/infrastructure/asr/' && exit 1 || echo "no ASR bypass"

# Frontend fetch direction
grep -RnE '\bfetch\(' frontend/src/components frontend/src/app frontend/src/hooks 2>/dev/null && exit 1 || echo "no fetch outside services"

# Frontend atom isolation
grep -RnE '@/services|@/hooks' frontend/src/components/atoms/ && exit 1 || echo "atoms clean"

# Infrastructure mount components stay isolated
grep -RE '@/services|@/hooks' frontend/src/components/_*/ 2>/dev/null && exit 1 || echo "infra mounts clean"
```

## 4. Changing this rule

Per `local-llm-and-phi.md` §7 (we extend the same discipline here):

1. An ADR in `docs/adr/`.
2. Approval recorded as the ADR's Status field flipping to Accepted.
3. The corresponding handoff that referenced the old rule is invalidated; Planner re-issues.

## 5. Refusal triggers (Generator)

The Generator MUST refuse the task and bounce it back to Planner when:

- A SPEC Block requires the backend to call `http://llm` / `http://asr` from outside the infrastructure layer.
- A SPEC Block requires a frontend atom to fetch data.
- A SPEC Block requires `app/domain/` to import from `app/infrastructure/`.
- The Generator cannot meet G7 without violating the directions above.

## 6. Anti-patterns

- "Just one direct httpx call from the router — it's small." The boundary is the rule; size is irrelevant.
- Re-exporting infra classes through `app/usecases/__init__.py` to dodge the import rule. The errors.py re-export is the documented exception; widening it requires an ADR.
- Atoms that fetch via SWR / React Query "because hooks are inside the atom". Move it to a molecule or up.
- Pages with `useEffect(() => { fetch(...) }, [])`. Move to a service via a hook.

## 7. Related documents

- `CLAUDE.md` §5 — high-level mapping (this rule supersedes for binding clauses).
- `backend/SPEC.md#layer-boundaries` — backend-specific elaboration (still binding).
- `frontend/SPEC.md#layer-rules` — frontend-specific elaboration (still binding).
- `local-llm-and-phi.md` §2 — inference-layer boundary (overlapping clause; this rule extends to ASR).
- `docs/dod-and-gates.md` G7 — gate ownership.
- `.claude/skills/security-check/SKILL.md` — verification recipe.
