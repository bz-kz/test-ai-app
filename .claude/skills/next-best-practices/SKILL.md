---
name: next-best-practices
description: Use during Evaluator G6/G7 review of any Block that touches frontend/src/app/** or page-level Next.js wiring. Checks Next.js 15+ App Router patterns — server/client split, data-fetching layer, metadata, caching directives, routing, accessibility — against project conventions in frontend/SPEC.md.
---

# next-best-practices

Evaluation checklist for Next.js 15+ App Router code in this project. The Evaluator invokes this skill when a Block's diff touches `frontend/src/app/**`, `route.ts`, layouts, or Server Actions. Findings feed the G7 (Architecture) and G6 (Spec alignment) gates per `docs/dod-and-gates.md`.

## Required reading

1. `frontend/SPEC.md` — atomic-design mapping, layer rules, latency UX budget.
2. `.claude/rules/local-llm-and-phi.md` §4 — frontend PHI storage prohibitions.
3. The Block's `Reference SPEC` anchor and the diff under review.

## Project pins

- Next.js: 15+ (App Router, React 19 RC compatible).
- TypeScript: strict; no `any`.
- Styling: Tailwind only (no CSS Modules / styled-components in the same component).
- Routing: file-system, `app/` directory.
- HTTP layer: `src/services/` is the only place that calls `fetch`.

## Checklist — each item maps to observable evidence

### 1. Server / Client boundary

- [ ] `"use client"` is at the top of a file only when it imports a React state/effect/ref hook, a browser-only API, or an event handler. Pages, layouts, and `route.ts` start server-side. **Verify:** `grep -RnE '^"use client"' frontend/src/app frontend/src/components`.
- [ ] Hooks (`useState`, `useEffect`, `useReducer`, `useRef`, `useContext` of a client provider, `useLayoutEffect`) appear only in `"use client"` files. **Verify:** for each match of those identifiers, the file's first non-comment line is `"use client"`.
- [ ] Server components do not import client-only libraries (anything that touches `window`, `document`, `localStorage`).
- [ ] Async server components (`async function Page()` style) return JSX; they do not call `useEffect` for data fetching.

### 2. Data fetching

- [ ] Server-side data fetching uses native `fetch` (Next.js caches it) or a service function from `src/services/`. **No** in-component `useEffect(fetch)` for initial render — that pattern belongs to client widgets after hydration.
- [ ] PHI-sensitive fetches set `{ cache: 'no-store' }` or `{ next: { revalidate: 0 } }`. Document the choice with a one-line comment when non-obvious.
- [ ] Cached fetches state the revalidation interval explicitly. `revalidate: false` (forever) is a smell unless justified.

### 3. Routing

- [ ] Each route segment has a single `page.tsx`. No mixing of `page.tsx` with an orphan `index.tsx`.
- [ ] Dynamic segments use `[slug]` or `[...slug]`. Optional catch-all is `[[...slug]]` only when the empty case is part of the contract.
- [ ] `loading.tsx` exists for any route whose data fetch may exceed `frontend/SPEC.md#latency-ux-budget` 1–3 s tier.
- [ ] `error.tsx` exists for routes whose handler can throw; `not-found.tsx` exists for routes that call `notFound()`.

### 4. Metadata

- [ ] Pages/layouts export `metadata` (static) or `generateMetadata` (dynamic). `<title>` and `<meta name="description">` are NOT hand-rolled in JSX.
- [ ] No PHI in any metadata field — title, description, OG tags, structured data. This is a PHI-rule §4 cross-check.

### 5. Layer rules (project-binding, from `frontend/SPEC.md`)

- [ ] No `fetch(` inside `frontend/src/components/**` or `frontend/src/app/**/page.tsx`. **Verify:** `grep -RnE '\bfetch\(' frontend/src/components frontend/src/app` returns 0 hits in production code (test files OK).
- [ ] Atom/molecule/organism placement matches `frontend/SPEC.md#atomic-design-mapping`. A molecule that imports another molecule is a smell unless documented.
- [ ] No `any`. Use `unknown` and narrow at the boundary. **Verify:** `grep -RnE ': any\b|<any>' frontend/src` returns 0 in production code.

### 6. PHI rule cross-check

- [ ] No PHI written to `localStorage` / `sessionStorage` / `indexedDB` / cookies. **Verify:** `grep -RnE 'localStorage|sessionStorage|indexedDB|document\.cookie' frontend/src` — every hit must be justified non-PHI.
- [ ] No PHI in URL query params, `next/navigation` route push, or `searchParams` echoed into pages without the project's `maskPhi` utility.

### 7. Accessibility

- [ ] WCAG 2.2 AA: every interactive atom has an accessible name (visible label, `aria-label`, or `<label>` association).
- [ ] No `<div onClick>` for actionable elements; use `<button>` or `<a>`.
- [ ] Focus order follows DOM order; `tabIndex={-1}` only for `aria-hidden` decorative content.
- [ ] Form fields use `<label htmlFor>` or `aria-labelledby` — not placeholder-as-label.

## Anti-patterns to flag

- `"use client"` at the top of a layout or route that does no interactive work.
- `useEffect(fetch)` for initial page data instead of an async server component or a service call.
- Hand-rolled `<title>` / `<meta>` tags in JSX.
- `// @ts-expect-error` / `// @ts-ignore` without an inline reason AND a `NOTES.md` follow-up reference.
- `next/dynamic` used to silence a build error rather than to lazy-load a heavy interactive widget.
- Console errors during `next dev` or `next build` on the affected route.
- Importing from `frontend/src/components/atoms/*` into a page without going through `molecules` or `organisms` (skips composition).

## Verification commands (run via Bash)

```bash
# Server / client boundary
grep -RnE '^"use client"' frontend/src/app frontend/src/components 2>/dev/null
grep -RnE 'useState|useEffect|useReducer|useRef|useLayoutEffect' frontend/src/components 2>/dev/null

# Layer rule: no fetch in components/pages
grep -RnE '\bfetch\(' frontend/src/components frontend/src/app 2>/dev/null

# Type safety
grep -RnE ': any\b|<any>' frontend/src 2>/dev/null

# PHI storage / URL leakage
grep -RnE 'localStorage|sessionStorage|indexedDB|document\.cookie' frontend/src 2>/dev/null
```

## Output the Evaluator folds into its QA Block

Return one of:

- `next-best-practices: PASS` — no findings.
- A bullet list of findings, each tagged `[BLOCKER]` / `[WARN]` / `[NOTE]`:
  - `[BLOCKER] <file>:<line> — <observed>; rule: <one-line>` for any item that fails the G7 Architecture or PHI cross-check threshold.
  - `[WARN]` for items that violate `frontend/SPEC.md` but are not security/architecture blockers.
  - `[NOTE]` for stylistic suggestions the Generator may track in a follow-up Block.

`[BLOCKER]` findings feed into the Evaluator's `## QA Failure` Block as G7 (Architecture) failures. `[WARN]` does not auto-fail unless paired with G6 (Spec alignment) by quoting the violated `frontend/SPEC.md` bullet.
