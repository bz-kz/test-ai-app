---
name: react-best-practices
description: Use during Evaluator G6/G7 review of any frontend Block that introduces or modifies React components, hooks, or services. Checks hooks rules, render performance, state ownership, controlled inputs, accessibility, and testing patterns against frontend/SPEC.md.
---

# react-best-practices

Evaluation checklist for React 18+/19 code in this project. The Evaluator invokes this skill when a Block's diff touches `frontend/src/components/**`, `frontend/src/hooks/**`, or `frontend/src/services/**`. Pairs with `next-best-practices` (App Router) and `frontend/SPEC.md`. Findings feed G7 (Architecture) and G6 (Spec alignment).

## Required reading

1. `frontend/SPEC.md` — atomic-design mapping, AI Output Patterns, latency UX budget.
2. `DESIGN.md` — AI Indicator, ConfidencePill, action affordances.
3. `.claude/rules/local-llm-and-phi.md` §4 — PHI in browser storage.
4. The Block's `Reference SPEC` anchor and the diff under review.

## Project pins

- React: 18+ (compat with 19 RC).
- State: prefer local `useState` + `useReducer`; no Redux unless an ADR is filed.
- Server state: lives behind a service in `src/services/`; UI subscribes via a hook in `src/hooks/`.
- Styling: Tailwind utility classes; no inline `style={{ ... }}` for layout (only for measured dynamic values).
- Testing: Vitest + Testing Library; `@testing-library/jest-dom` matchers.

## Checklist — each item maps to observable evidence

### 1. Hook rules (Rules of Hooks)

- [ ] Hooks are called at the top level of a component or another hook. Not inside `if`, `for`, or `try`. **Verify:** `grep` for `useState\(`, `useEffect\(` inside conditional bodies — should be zero in production code.
- [ ] Hook names start with `use` and live in `src/hooks/` if reused across components. One-off hooks may live next to the consuming component.
- [ ] `useEffect` dependency arrays are exhaustive. Omitted deps require an inline reason comment AND `eslint-disable-next-line react-hooks/exhaustive-deps` on the immediate line.
- [ ] No effect runs on every render (an effect with no dependency array — `useEffect(fn)` — is a smell unless intentional and commented).

### 2. State ownership and lift

- [ ] State lives at the lowest common ancestor that needs it. A piece of state used by exactly one component MUST NOT be lifted to a parent or context.
- [ ] Server state (data fetched from the backend) does NOT live in `useState` initialised from a fetch. Use the service + hook pattern (`useXyz` returns `{data, status, error}`).
- [ ] Refs (`useRef`) are used for imperative DOM access or storing mutable values that should not trigger re-renders. They are NOT used as a substitute for `useState`.

### 3. Render performance

- [ ] `useMemo` / `useCallback` are used only when there is a measurable need: passing stable references into memoized children, or wrapping expensive pure computations. Reflex use everywhere is a smell.
- [ ] `React.memo` wraps a leaf component only when the parent re-renders frequently with the same props.
- [ ] List items have a stable `key` prop. `key={index}` is allowed only when the list is append-only and never reordered.
- [ ] No inline object/array literals in props of memoized children (defeats the memo).

### 4. Controlled inputs

- [ ] Form inputs are controlled (`value` + `onChange`) unless the component is explicitly an uncontrolled wrapper documented as such.
- [ ] Numeric inputs validate at the boundary; the state type matches the user's intent (`number | ''` for an optional numeric field, not `string`).
- [ ] No `defaultValue` on a controlled input — that triggers a React warning and indicates a mistake.

### 5. Effects — what NOT to do

- [ ] No `useEffect` to derive state from props. Compute it in render or with `useMemo`.
- [ ] No `useEffect` to call a service whose response is required for first paint. That belongs in a server component or a hook that gates the UI behind a `status === 'success'` discriminator.
- [ ] No `useEffect` to "sync" props with state. Lift state up or pass the prop down directly.

### 6. Accessibility

- [ ] Atom interactive elements (`Button`, `Input`, `Checkbox`, etc.) accept and forward `aria-*` props.
- [ ] `Button` renders an actual `<button>` (or a `<button>` wrapped via `forwardRef`). Not a `<div>` with `role="button"`.
- [ ] Disabled state uses `disabled` (interactive elements) or `aria-disabled` (read-only signal); they do not conflict.
- [ ] Focus management on dynamic content: opening a dialog moves focus into the dialog; closing returns focus to the trigger.
- [ ] No `outline: none` without a replacement focus ring.

### 7. AI output patterns (project-specific, `frontend/SPEC.md#ai-output-patterns`)

- [ ] AI-generated text is rendered through `<AIIndicatedText>` (left border + AI icon). Plain `<p>{aiText}</p>` is a violation.
- [ ] Confidence ≤ 0.5 surfaces `<ConfidencePill variant="warning">`.
- [ ] Each AI block exposes Regenerate / Edit / Approve affordances when the Block calls for them.

### 8. Testing

- [ ] Tests assert behaviour visible to a user (text, role, label) — not implementation details (state shape, internal hook return values).
- [ ] Query priority: `getByRole` > `getByLabelText` > `getByText` > `getByTestId` (last resort).
- [ ] `userEvent` is preferred over `fireEvent` for user-driven interactions.
- [ ] Tests of components that fetch use the project's service mock — not raw `fetch` mocks scattered across files.
- [ ] Coverage of the Block's stated UX states (idle, loading, error, success) is verified by named tests.

### 9. PHI cross-check

- [ ] No PHI in `console.*` calls. **Verify:** `grep -RnE 'console\.(log|info|warn|error|debug)' frontend/src` — each hit must be either non-PHI or wrapped in `maskPhi(...)`.
- [ ] No PHI in `localStorage` / `sessionStorage` / `indexedDB` / cookies — covered by `next-best-practices` §6.
- [ ] No PHI in error boundaries' fallback UI.
- [ ] No raw-HTML injection prop (the React escape hatch that bypasses JSX escaping) for any content that could carry PHI or untrusted strings. Each occurrence requires an ADR.

## Anti-patterns to flag

- Putting `useState`/`useEffect` in a server component (would fail at compile time but worth checking the file boundary).
- Using `useState` to mirror a prop.
- `useEffect` that calls `setState` unconditionally (causes a re-render every commit).
- `useMemo`/`useCallback` everywhere without measurement.
- `React.memo` on a component whose parent never re-renders.
- The raw-HTML React injection prop used on any content path — auto-block unless an ADR exists.
- Inline `style={{}}` for static layout (Tailwind class is the convention).
- Tests that read `.state()` or call private methods on a class component.
- Tests that assert on `getByTestId` when a `getByRole` is available.

## Verification commands (run via Bash)

```bash
# Hook conditional usage (heuristic)
grep -RnE 'if \(.+\) \{\s*$' frontend/src 2>/dev/null | head

# Effect with no deps array
grep -RnE 'useEffect\(\s*\(\)\s*=>\s*\{' frontend/src 2>/dev/null

# PHI in console
grep -RnE 'console\.(log|info|warn|error|debug)' frontend/src 2>/dev/null

# Raw-HTML injection prop (React escape hatch)
grep -RnE 'dangerously[A-Za-z]+HTML' frontend/src 2>/dev/null

# Type safety
grep -RnE ': any\b|<any>' frontend/src 2>/dev/null
```

## Output the Evaluator folds into its QA Block

Return one of:

- `react-best-practices: PASS` — no findings.
- A bullet list of findings, each tagged `[BLOCKER]` / `[WARN]` / `[NOTE]`:
  - `[BLOCKER]` for rules-of-hooks violations, PHI leakage to console/storage, the raw-HTML escape hatch used with untrusted content, or AI Output Patterns missing on AI-rendered text.
  - `[WARN]` for state-shape mismatches, missing keys, missing a11y attributes.
  - `[NOTE]` for performance opportunities and test-quality suggestions.

`[BLOCKER]` findings feed the Evaluator's `## QA Failure` Block as G7 (Architecture) or, when traced to `frontend/SPEC.md`, G6 (Spec alignment).
