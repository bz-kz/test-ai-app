# ADR 0006: Hybrid observability — OTel for server runtimes, Datadog RUM for browser

- **Status:** Accepted
- **Date:** 2026-05-22
- **Owner:** Planner (Claude Opus 4.7)
- **Related Spec:** `CLAUDE.md` §2 (tech stack), `docker-compose.yml` (Datadog Agent block, lines 7–26, 60–92, 142–169, 293–469), `.claude/rules/local-llm-and-phi.md` §1 (egress)

## Context

`docker-compose.yml` documents an architectural intent (lines 7–11): "アプリは OpenTelemetry SDK で計装 → DD Agent の OTLP receiver で受信 → Datadog SaaS へ転送 (アプリのコードはベンダー非依存に保つ)." The compose file wires every consumable end of that contract: DD Agent's OTLP HTTP receiver on `0.0.0.0:4318` (line 378), the matched `OTEL_*` env vars on backend (lines 152–169) and frontend (lines 67–92), and DD Agent PHI obfuscation rules for inbound traces (lines 345–372) and logs (lines 419–425).

Two implementation gaps and one user-driven re-scope:

1. **Backend used Datadog-proprietary SDK.** `backend/main.py:2` was performing `import ddtrace.auto`, activating ddtrace and shipping traces to DD Agent's APM port 8126 in Datadog's native protocol — bypassing the OTLP path. BE-018 migrates this to OTel auto-instrumentation per this ADR.
2. **Frontend had no telemetry at all.** A first attempt to add `@datadog/browser-rum` (commit reverted prior to this ADR) was rolled back because of incorrect Vite syntax, module-top-level `init()` in a Server Component, and missing env wiring. The SDK itself was not the issue.
3. **User asked for a hybrid model.** After exploring a pure-OTel approach (server + browser), the user explicitly requested: **frontend だけは Datadog RUM にして、backend は OTel を使うハイブリッド構成**. The motivation is to retain Datadog RUM-only features (Session Replay with full DOM masking, Core Web Vitals auto-collection, RUM-action funnels) for the browser while keeping the backend (and the frontend Node runtime) on vendor-neutral OTel so a future Datadog → other-vendor migration is one DD Agent reconfiguration plus replacing exactly one browser SDK file, not a full backend rewrite.

Without a binding ADR, the next iteration risks repeating the previous failure modes: another revert of a botched RUM init, or quiet re-introduction of ddtrace in backend. This ADR codifies the **single hybrid decision** so future Generators cannot drift in either direction.

## Decision

We will instrument observability with a hybrid library policy:

- **Server runtimes (both backend FastAPI and frontend Next.js Node runtime):** exclusively via the **OpenTelemetry SDK** over **OTLP HTTP/protobuf**, sending to the in-network `datadog-agent:4318` receiver.
- **Frontend browser runtime:** exclusively via **`@datadog/browser-rum`** (and, when needed for non-trace telemetry, `@datadog/browser-logs` — but logs are out of scope for v1 per `local-llm-and-phi.md` §3). RUM ships directly to Datadog SaaS (`browser-intake-<DD_SITE>`), not via the local DD Agent. No OTel browser SDK is used.

Concretely:

- **Backend (FastAPI) — BE-018:** Use `opentelemetry-distro[otlp]` with `opentelemetry-instrumentation-{fastapi,httpx,sqlalchemy,asyncpg,logging}`. Launch via `opentelemetry-instrument uvicorn main:app --host 0.0.0.0 --port 8000`. `import ddtrace.auto` removed; `ddtrace` removed from `requirements.txt`. Explicitly: `OTEL_METRICS_EXPORTER=none` and `OTEL_LOGS_EXPORTER=none` set in compose to suppress non-trace exporters (DD Agent OTLP metrics/logs receivers are off in v1 — see DD Agent config notes below).
- **Frontend server runtime (Next.js Node) — FE-014:** Use `@vercel/otel` from a top-level `frontend/instrumentation.ts`. `@vercel/otel` wires Node `http`/`undici` auto-instrumentation; server-side outbound fetch to backend automatically propagates W3C `traceparent`. Reuses the existing compose `OTEL_*` env vars (no new vars).
- **Frontend browser runtime — FE-015:** Use `@datadog/browser-rum` initialized once from a single `"use client"` client island injected from `app/layout.tsx`. Init parameters come from `NEXT_PUBLIC_DD_RUM_*` build-time env vars (new), with strict PHI safeguards (catalog below). The init is gated by a feature flag (`NEXT_PUBLIC_RUM_ENABLED`) so the SDK can be shipped without an active RUM application registered in Datadog's UI.
- **DD Agent — supporting change:** `DD_OTLP_CONFIG_TRACES_ENABLED: "true"`, `DD_OTLP_CONFIG_METRICS_ENABLED: "false"`, `DD_OTLP_CONFIG_LOGS_ENABLED: "false"` to enable the trace pipeline only. `DD_PROCESS_AGENT_ENABLED: "true"` (flipped from `"false"`) because DD Agent's OTLP ingest pipeline registers process metrics at startup and fails to initialize otherwise (`failed to register process metrics: process does not exist` — observed during BE-018 G0, 2026-05-22). Image pinned to `gcr.io/datadoghq/agent:7.66.1` because `7.79.0` exhibits the same OTLP pipeline init failure even with process agent enabled (likely arm64 + recent collector contrib version interaction). The privacy trade-off of exposing the dev machine's process list to Datadog is accepted for the PoC; production should revisit if applicable.
- **Trace context propagation:** W3C `traceparent` everywhere. `@datadog/browser-rum`'s `allowedTracingUrls` is configured to inject `traceparent` (not the Datadog-only `x-datadog-*` headers) into outbound fetches to the backend, so the trace continuity browser → backend works cleanly with backend OTel.

### Bans (binding)

The following imports / requires / `pnpm add` / `pip install`s are forbidden at runtime in any layer:

- `dd-trace` (Node) — the `dd-trace-js` package, even in a frontend Node runtime variant
- `ddtrace` (Python) — including `import ddtrace`, `import ddtrace.auto`
- `@opentelemetry/sdk-trace-web`, `@opentelemetry/exporter-trace-otlp-http`, `@opentelemetry/instrumentation-{fetch,document-load,user-interaction}` and any other OTel browser SDK package in the browser runtime. Browser telemetry is RUM-only.

Detection is a CRITICAL G7 (Architecture) finding. The `security-check` skill's probe matrix is extended (see Open follow-ups §1). Tests MAY import these for fixture purposes if quarantined under `**/test-fixtures/` and the fixture is never bundled into the production image.

### Allowed (this ADR's central exception to the compose "OTel-only" intent)

- `@datadog/browser-rum` in the browser runtime, **only via the designated init module** (`frontend/src/lib/datadog-rum.ts` per FE-015) and the single client-island mount (`frontend/src/components/_rum/RumInit.tsx`). Direct import from any other file is a G7 violation, enforced by grep (see Open follow-ups).
- `@datadog/browser-logs` — out of scope for v1 (logs and PHI deserve their own ADR). Add to the ban list above when v1 ships if not used.
- The Datadog Agent (`gcr.io/datadoghq/agent:7.66.1` per above) stays in compose as the OTLP receiver for server traces and the metrics/checks scraper. It is infrastructure, not an SDK we ship.
- The Datadog Agent's existing PHI obfuscation rules (compose lines 345–372: `DD_APM_OBFUSCATION_HTTP_REMOVE_QUERY_STRING`, `..._REMOVE_PATH_DIGITS`, `..._SQL_REPLACE_DIGITS`, `DD_APM_REPLACE_TAGS`) apply to OTLP-ingested traces from server runtimes. They do NOT apply to RUM payloads (RUM bypasses DD Agent and POSTs to Datadog SaaS directly). Therefore RUM needs in-SDK scrubbing (egress contract below) — the DD Agent rules are not a safety net for browser data.

### Egress contracts (binding)

**Server-side OTel (BE-018, FE-014):** Traces only, sent to `datadog-agent:4318`. DD Agent's existing obfuscation handles URL paths / query strings / SQL digit literals / tag values. No additional in-SDK scrubbing is required because the DD Agent receives the traces before they leave the local Docker network and applies the rules before forwarding to Datadog SaaS.

**Browser RUM (FE-015):** RUM payload posts directly from the user's browser to `browser-intake-<DD_SITE>.datadoghq.com` over HTTPS. The DD Agent is not in the path. Therefore the **in-SDK scrub contract is the only line of defense**:

- **Allowed in RUM payloads:**
  - `view.url` — but only in **template form** (e.g. `/patients/:patientId`, `/encounters/:encounterId/draft`). The `beforeSend` hook rewrites `event.view.url` and `event.view.name` through the URL scrub catalog defined in `lib/datadog-rum.ts`.
  - `resource.url` — also template form via the same scrub.
  - `error.type`, `error.source`, `error.handling`
  - Page load timings, Core Web Vitals (LCP, INP, CLS, FCP, TTFB)
  - HTTP method, status code, duration
  - `user.id` set exclusively to the string `"anon"` (so RUM can produce session-grouped views without exposing any PHI identifier)
  - Session Replay: enabled at `sessionReplaySampleRate: 20` with `defaultPrivacyLevel: "mask"` (all text masked at capture time, including labels — not just user input). See PHI section below for the per-route mask-attribute checklist.
- **Forbidden in RUM payloads:**
  - Raw `view.url` containing PHI segments (must go through scrub before assignment)
  - `error.message` and `error.stack` containing 4+ consecutive digit sequences (digit-scrub before passing to RUM via the `beforeSend` hook)
  - Custom attributes set via `addAction`, `addError`, `setUser` (other than `id: "anon"`), `setGlobalContext` if the value contains PHI
  - `resource.url` for any URL that is not `NEXT_PUBLIC_API_BASE_URL`-prefixed (RUM's `allowedTracingUrls` limits `traceparent` injection accordingly; resources from third-party CDNs / analytics scripts / etc. should not appear in PHI surfaces of this PoC)
  - Long-task spans containing CPU stack frames with embedded PHI literals (no v1 long-task tracking — `trackLongTasks: false` until per-PHI-route audit completes)
  - Session Replay DOM nodes from PHI-bearing elements that have not been audited and annotated with `data-dd-privacy="mask"` or `data-dd-privacy="hidden"` (see PHI checklist)

## Consequences

- **Positive:**
  - Backend telemetry is no longer Datadog-protocol-locked. Switching the backend to any OTLP-compatible store is a compose-layer change with zero application code touched.
  - Trace propagation from frontend Node runtime to backend uses standard W3C `traceparent`; no Datadog-specific shim is required at the server boundary.
  - Browser observability gains Session Replay, Core Web Vitals, and RUM action funnels — features for which there is no off-the-shelf OTel browser equivalent. The user's diagnostic workflows for clinician UX issues can use these directly.
  - The compose-stated architectural intent for the server side ("OTel only, ベンダー非依存") becomes binding. Backend cannot quietly drift back to ddtrace because the `security-check` probe matrix grep catches it.
  - The hybrid boundary is concentrated in exactly one frontend file (`lib/datadog-rum.ts`) and one mount (`components/_rum/RumInit.tsx`). Replacing RUM with another browser RUM vendor later is small-surface work; the rest of the app is untouched.

- **Negative:**
  - The frontend now imports a Datadog-proprietary SDK (~80–120 kB gzipped). This is the vendor-lock we explicitly accepted in exchange for Session Replay et al. Bundle size impact is measurable but within PoC budget; if it becomes a problem, the `NEXT_PUBLIC_RUM_ENABLED=false` build flag drops the SDK via dynamic-import gating.
  - The hybrid means two different telemetry "shapes" land in Datadog: APM traces (from server OTel) and RUM events (from browser SDK). Connecting them in the Datadog UI requires that `traceparent` is propagated browser → backend (configured via `allowedTracingUrls`). The configuration is a single line; the verification path (open DevTools, confirm `traceparent` header on backend calls) is part of FE-015 G0.
  - Session Replay is the largest PHI egress surface we open in this project. Even with `defaultPrivacyLevel: "mask"`, DOM-position information (where a masked block is, of what shape and size) can in principle leak identity hints. We accept this trade-off because (a) the masking is aggressive (`mask`, not `mask-user-input` — mask EVERY text), (b) `sessionReplaySampleRate: 20` means only 1-in-5 sessions are replayed, (c) the per-PHI-route audit (Open follow-ups §6) gives us a paper trail when a new route is added. **A future ADR may downgrade Session Replay to 0% if any leak is observed in audit.**
  - DD Agent process agent is now enabled (`DD_PROCESS_AGENT_ENABLED: "true"`), exposing the dev machine's process list to Datadog. Was previously off for individual-developer privacy. Trade-off documented in the compose comment block and the §Decision above.
  - Frontend `app/page.tsx`'s previous attempt at RUM (Vite syntax, top-level Server Component init) MUST NOT recur. The single-init module + client-island pattern is the only allowed initialization shape; deviation is a G7 violation.

- **Reversibility:**
  - **Backend OTel → ddtrace** is moderate: revert `backend/Dockerfile`, `backend/main.py`, `backend/requirements.txt`, three small edits and a rebuild.
  - **Browser RUM → none** is easy: set `NEXT_PUBLIC_RUM_ENABLED=false` and rebuild frontend; the SDK code stays but the init is gated off. Full removal is delete of `lib/datadog-rum.ts` + `components/_rum/` + the layout mount.
  - **Hybrid → pure OTel (server-side everywhere, no browser telemetry, OR with OTel browser SDK)** is a larger operation matching the alternative not chosen here. Tracked as a possible future ADR if the RUM feature surface stops justifying the vendor lock.

## Alternatives considered

- **Pure OTel for both server and browser.** Rejected after user pivot — Session Replay, Core Web Vitals auto-collection, and RUM action funnels are RUM-only features the user wants. OTel browser SDK ecosystem has no equivalent.
- **Pure Datadog (ddtrace on backend + RUM on browser).** Rejected — keeps the backend vendor-locked to Datadog with no offsetting benefit. ddtrace has no feature on the backend that OTel can't match for our usage; the asymmetry of OTel backend + RUM browser is intentional, not accidental.
- **OTel browser SDK + Datadog RUM in parallel (dual instrumentation).** Rejected — doubles browser bundle size, generates duplicate spans for every fetch, requires reconciliation of two different propagation header formats, and gives no information the RUM alone wouldn't have.
- **Skip backend migration; keep ddtrace.** Rejected — preserves the documented design-intent vs. implementation drift forever and traps us in vendor-lock at the server boundary, which is the boundary that's most painful to migrate later.
- **Use an OpenTelemetry Collector as a sidecar between server runtimes and DD Agent.** Rejected for v1 — adds a container and a config file for no current benefit. DD Agent 7.66.1's OTLP receiver is sufficient. Promotion to a dedicated Collector is the natural next step if we add OTel metrics + logs receivers (out of scope here).
- **Disable Session Replay (`sessionReplaySampleRate: 0`).** Rejected — the user explicitly chose "全 mask で有効化" (enable with full masking). The PHI safeguard is the masking, not the disablement. A future incident-driven ADR may revisit.

## Gates affected

- **G4 (Security / PHI):** New probes added to `security-check` skill's probe matrix (see Open follow-ups §1):
  - `grep -RnE '^import ddtrace' backend/app backend/main.py` MUST be empty
  - `grep -RE 'dd-trace' frontend/src` MUST be empty (no Node ddtrace in frontend)
  - `grep -RE '@opentelemetry' frontend/src` MUST be empty (no OTel browser SDK)
  - `grep -RE '@datadog/browser-' frontend/src | grep -vE '(lib/datadog-rum|components/_rum)'` MUST be empty (RUM SDK isolation)
  - `lib/datadog-rum.ts` MUST contain exactly one `setUser(` assignment, with literal `'anon'` value
  - `lib/datadog-rum.ts` MUST contain literal `defaultPrivacyLevel: 'mask'` (not `'mask-user-input'`)
  - `lib/datadog-rum.ts` MUST contain literal `trackLongTasks: false`
- **G5 (Cost / Inference budget):** unchanged. RUM SDK adds ~80–120 kB gz to first-load JS — within PoC budget. OTel Python instrumentation startup overhead is sub-second.
- **G6 (Spec alignment):** `backend/SPEC.md` gains an "Observability" section pointing at this ADR. `frontend/SPEC.md` gains the same plus the architectural placement note for `RumInit` (infrastructure mount in `_rum/`, not an atom).
- **G7 (Architecture):** Layer-direction rule (`.claude/rules/architecture-layer-direction.md` §2) verification commands extended: `grep -RE '@datadog/browser-' frontend/src` outside the two designated files is a violation. SDK isolation pattern is identical to the existing `LocalLLMClient` / `LocalASRClient` infrastructure-layer pattern.

## Open follow-ups

- [ ] `.claude/skills/security-check/SKILL.md` Probe matrix — Planner drafts new probe text inline; human applies (skill files are human-only per repo policy).
- [ ] `.claude/rules/local-llm-and-phi.md` §6 (verification commands) — Planner drafts new grep rows inline; human applies (rules are human-only).
- [ ] Generator implements `BE-018` (backend ddtrace → OTel migration) per the Block handoff that references this ADR. **DONE in the implementation session that drafted this ADR (2026-05-22).**
- [ ] Generator implements `FE-014` (frontend server-side OTel via `@vercel/otel`) per this ADR.
- [ ] Generator implements `FE-015` (frontend browser RUM with the PHI-safe init module) per this ADR. MUST wait until BE-018 + FE-014 are green so trace continuity verification has both ends in place.
- [ ] **Per-PHI-route Session Replay privacy audit** before flipping `sessionReplaySampleRate` above 0 in `.env`: walk each PHI-bearing route's rendered DOM and confirm every element that displays PHI carries `data-dd-privacy="mask"` (text masking) or `data-dd-privacy="hidden"` (element hidden in replay). Routes to audit: `/patients`, `/patients/[patientId]`, `/encounters/[encounterId]`, `/encounters/[encounterId]/draft`. The audit MUST happen before any session replay sample reaches Datadog. Tracked as a follow-up Block; FE-015 ships with `sessionReplaySampleRate: 20` per ADR's PHI defaults but rate flips to non-zero only after audit Block lands.
- [ ] On first FE-015 deployment, verify in DevTools Network that `traceparent` header is present on outbound fetches to `${NEXT_PUBLIC_API_BASE_URL}/*` and that the matching span shows up in Datadog APM linked to the corresponding RUM session.
- [ ] After RUM has run for ≥1 week against real PoC sessions, audit Datadog UI APM/RUM payloads to confirm zero PHI leakage (URL templates intact, no patient identifiers in `error.message`, no PHI text visible in Session Replay segments). If a leak is found, file a hot-fix Block and a superseding ADR.
- [ ] DD Agent `redisdb` check is timing out (no redis container) — noise in logs. Out of this ADR's scope; file a follow-up to disable the check via DD Agent config.
- [ ] OTel metrics + OTel logs receivers on DD Agent are explicitly disabled in v1. If/when added, this ADR should be referenced and may need a supplementary ADR for the PHI contract of those signal types.
