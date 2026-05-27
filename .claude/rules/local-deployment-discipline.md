# Rule: Local Deployment Discipline

This rule is binding. It codifies Docker Compose + Next.js deployment gotchas that have repeatedly caused silent staleness in this PoC (notably INF-005 / commit `022c9a6`). Violations are not always G0 failures — they manifest as "the test passes, but the live system runs old code". Audit trail and operator discipline are the only defence.

## 1. Image vs container distinction

Binding clause:

- **`docker compose up -d --force-recreate <svc>` does NOT rebuild the image.** It re-creates the container _from the existing image_. New code in the working tree will NOT reach the container.
- To reflect new code in the running stack, the sequence is:
  ```bash
  docker compose build <svc>
  docker compose up -d <svc>
  ```
  `up -d` re-creates the container if the image hash changed. Use `--force-recreate` only when you specifically need to recycle the container without an image change (env-var swap, host-mount swap).

Verification commands (run AFTER `up -d` to confirm the new code is live):

```bash
# Backend: spot-check a known-new identifier from the most recent commit
docker compose exec -T backend grep -c '<known-new-string>' /app/<known-file>

# Frontend: spot-check a baked NEXT_PUBLIC_* string or new route
docker compose exec -T frontend sh -c 'find /app/.next -name "*.js" 2>/dev/null | xargs grep -l "<known-new-string>"' | head -3
```

If the grep returns 0 hits when ≥1 is expected, the build step was skipped. Repeat `build → up -d`.

## 2. Next.js `NEXT_PUBLIC_*` env vars

Binding clause:

- **Next.js bakes `NEXT_PUBLIC_*` variables into the client JS bundle at `npm run build` time, NOT at runtime.**
- `docker-compose.yml`'s `environment:` block sets RUNTIME env vars. They are visible to server-side rendering and Node.js process code, but the **already-compiled client bundle** has whatever value was present during `npm run build` inside the `frontend` image.
- To make a `NEXT_PUBLIC_*` variable reach the client bundle:
  1. Declare an `ARG` in `frontend/Dockerfile` BEFORE `RUN npm run build`.
  2. Optionally `ENV` it from the `ARG` so subsequent build steps can read it.
  3. Pass the value via `docker-compose.yml` `frontend.build.args` (NOT `environment:`).
- If you want the value also available at runtime (SSR / Node), set it in BOTH `build.args` and `environment:`.

Required Dockerfile pattern:

```dockerfile
FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# NEXT_PUBLIC_* are baked at build; default falls back gracefully in constants.ts.
ARG NEXT_PUBLIC_API_BASE_URL
ARG NEXT_PUBLIC_ASR_STREAMING_ENABLED
ARG NEXT_PUBLIC_RUM_ENABLED
ARG NEXT_PUBLIC_DD_RUM_APPLICATION_ID
ARG NEXT_PUBLIC_DD_RUM_CLIENT_TOKEN
ARG NEXT_PUBLIC_DD_SITE
ARG NEXT_PUBLIC_DD_RUM_SERVICE
ARG NEXT_PUBLIC_DD_RUM_ENV
ARG NEXT_PUBLIC_DD_RUM_VERSION
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
ENV NEXT_PUBLIC_ASR_STREAMING_ENABLED=$NEXT_PUBLIC_ASR_STREAMING_ENABLED
ENV NEXT_PUBLIC_RUM_ENABLED=$NEXT_PUBLIC_RUM_ENABLED
ENV NEXT_PUBLIC_DD_RUM_APPLICATION_ID=$NEXT_PUBLIC_DD_RUM_APPLICATION_ID
ENV NEXT_PUBLIC_DD_RUM_CLIENT_TOKEN=$NEXT_PUBLIC_DD_RUM_CLIENT_TOKEN
ENV NEXT_PUBLIC_DD_SITE=$NEXT_PUBLIC_DD_SITE
ENV NEXT_PUBLIC_DD_RUM_SERVICE=$NEXT_PUBLIC_DD_RUM_SERVICE
ENV NEXT_PUBLIC_DD_RUM_ENV=$NEXT_PUBLIC_DD_RUM_ENV
ENV NEXT_PUBLIC_DD_RUM_VERSION=$NEXT_PUBLIC_DD_RUM_VERSION
ENV CI=true
RUN npm run build
```

Required `docker-compose.yml` pattern:

```yaml
frontend:
  build:
    context: ./frontend
    dockerfile: Dockerfile
    args:
      - NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
      - NEXT_PUBLIC_ASR_STREAMING_ENABLED=false
  environment:
    - NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
    - NEXT_PUBLIC_ASR_STREAMING_ENABLED=false
```

Adding a new `NEXT_PUBLIC_*` variable requires updating BOTH locations and rebuilding the image.

Verification (after build):

```bash
docker compose exec -T frontend sh -c 'find /app/.next -name "*.js" 2>/dev/null | xargs grep -l "<expected-baked-string>"' | head -3
```

A 0-hit result for an expected baked value means the build args wiring is broken.

## 3. Block QA smoke after deployment

Binding clause:

After Evaluator passes a Block that touches `Dockerfile`, `docker-compose.yml`, or `**/config.py`, the operator (main loop or human) MUST:

1. `docker compose build <affected-services>`
2. `docker compose up -d <affected-services>` (no `--force-recreate` unless intentional)
3. `curl -s http://localhost:8000/health` → 200 with all services reachable
4. Curl one Block-representative endpoint (e.g. POST to a new route) to confirm route loads (4xx is acceptable as long as it isn't 404 route-not-found).
5. For frontend changes affecting the user-facing UI, navigate to a representative page and confirm no console errors beyond known favicon 404.

If any step fails, treat the Block as not actually deployed despite QA Pass — file a follow-up Block (typically `INF-NNN` infrastructure / deployment fix).

## 4. Image size budget (informative, not gating)

These are operating points, not hard thresholds. Flag deviations in cost-check ADVICE:

- `backend`: ~500 MB pre-BE-016 → ~1.08 GB post-BE-016 (ffmpeg apt install). Accepted for PoC.
- `frontend`: ~200 MB (Next.js standalone output).
- `asr`: ~220 MB (whisper.cpp source build, multi-stage).
- `llm`: ~5 GB (Ollama base + gemma4:e4b weights via volume).
- `postgres`: ~300 MB (postgres:16-alpine).

Total local-stack disk footprint: ~7 GB images + ~10 GB volume data (gemma weights + whisper weights + postgres data).

## 5. Refusal triggers (Generator)

The Generator MUST refuse the task and bounce it back to Planner when:

- A SPEC Block introduces a new `NEXT_PUBLIC_*` variable WITHOUT specifying both `build.args` AND `environment:` placement.
- A SPEC Block describes a deployment step using `--force-recreate` to "pick up code changes" — that's the bug class this rule exists to prevent.
- An operator instruction says "the env var should be enough" for a Next.js client variable without the build args.

## 6. Anti-patterns

- "The container restarted, so the new code is live." Restart re-runs the entrypoint with the SAME image. It does not rebuild.
- "I added the env var to compose, it should work." For `NEXT_PUBLIC_*`, runtime env is insufficient. Build args is the contract.
- Using `docker compose down && up -d --build` reflexively. It works but tears down volumes unnecessarily; `docker compose build <svc> && up -d <svc>` is targeted.
- Skipping the post-deploy curl smoke because "the unit tests pass". Unit tests don't load the live container.

## 7. Changing this rule

Per `local-llm-and-phi.md` §7 discipline:

1. An ADR in `docs/adr/`.
2. ADR Status: Accepted.
3. Re-issue handoffs referencing the old rule.

## 8. Related documents

- `docs/runbook-local-dev.md` — operator step-by-step (cross-reference).
- `docker-compose.yml` — concrete topology (must align with §1, §2).
- `frontend/Dockerfile` — build args pattern (must match §2).
- `docs/dod-and-gates.md` G0 — Compose-up gate.
- `.claude/rules/local-llm-and-phi.md` §1 — egress boundary (related; this rule is about _getting code deployed_, that rule is about _what code is allowed to send where_).
