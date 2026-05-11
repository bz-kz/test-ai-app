---
name: docker-best-practices-master
description: Use during Evaluator G0/G6/G7 review of any Block that touches docker-compose.yml, Dockerfile(s), .dockerignore, or container-only configuration (entrypoints, healthchecks, env files). Checks container hygiene — image size, layer cache, multi-stage builds, non-root user, healthchecks, network isolation, secrets handling — against project conventions and PHI rule §1.
---

# docker-best-practices-master

Evaluation checklist for Docker / docker-compose code in this project. The Evaluator invokes this skill when a Block's diff touches:

- `docker-compose.yml`
- `frontend/Dockerfile`, `backend/Dockerfile`, or any other `Dockerfile`
- `.dockerignore` (root or per-service)
- Container entrypoints / health probes / env files referenced from compose

Findings feed G0 (Compose-up), G4 (Security / PHI — network isolation), G7 (Architecture — image layout), and G6 (Spec alignment — `SPEC.md#runtime-topology`).

## Required reading

1. `SPEC.md#runtime-topology` — service shape, port-publishing rule.
2. `docs/runbook-local-dev.md` — operational steps for the same topology.
3. `.claude/rules/local-llm-and-phi.md` §1 — network egress rules; `llm`/`postgres` MUST stay internal.
4. The Block's `Reference SPEC` anchor and the diff under review.

## Project pins (binding from SPEC.md)

- Services: `frontend`, `backend`, `postgres`, `llm`.
- Public ports: only `frontend` (3000) and `backend` (8000). `postgres` and `llm` are internal-only.
- LLM image: Ollama; model tag `gemma4:e4b`. Model variant changes require an ADR.
- Healthy in ≤120 s on a developer machine (G0 threshold).
- `docker compose down -v` is forbidden in agents.

## Checklist — each item maps to observable evidence

### 1. Compose: network isolation (PHI rule §1, G4 cross-check)

- [ ] No `ports:` mapping on `postgres` or `llm` to the host. **Verify:** `grep -nE '"5432:5432"|"11434:11434"' docker-compose.yml` returns 0 hits.
- [ ] No `extra_hosts:` resolving to public IPs anywhere. **Verify:** `grep -nE 'extra_hosts|host\.docker\.internal' docker-compose.yml` returns 0 hits.
- [ ] `postgres` and `llm` are attached to an `internal: true` bridge network (or equivalent). The `frontend`/`backend` may join the same network for service-name reachability but only `frontend`/`backend` publish to the host.
- [ ] Backend can resolve `llm` and `postgres` by service name; no IP literals in code or env.

### 2. Compose: service definitions

- [ ] Every service defines an `image:` or `build:` — never both pointed at moving targets (`build` with `image: x:latest` is a smell).
- [ ] Image tags are pinned to a specific version, NOT `:latest`. The model tag `gemma4:e4b` is acceptable because the project pins to that variant (per `SPEC.md#inference-layer-contract`).
- [ ] Each service has a `healthcheck:` with `interval`, `timeout`, `retries` that lets `docker compose up -d --wait` reach a healthy state inside the 120 s budget.
- [ ] `restart:` policy is explicit (`unless-stopped` or `on-failure`); not relying on the default.
- [ ] `depends_on:` uses the long form with `condition: service_healthy` for services that must be ready (not just started) before the depending service comes up.
- [ ] Environment is supplied via `env_file:` or explicit `environment:` keys — secrets are NOT inlined as literal values. Use `${VAR}` interpolation from `.env` (which is gitignored) or compose `secrets:`.

### 3. Compose: volumes & state

- [ ] Stateful data (postgres data dir, model cache) sits on named volumes — not on a bind mount into the developer's home directory by default.
- [ ] No bind mount that would let a host process write into a container's `/etc` or binary paths.
- [ ] No `:cached`/`:delegated` mount flags relied upon for correctness (they are macOS-only ergonomics).

### 4. Dockerfile: build hygiene

- [ ] Multi-stage build for application services: a `builder` stage installs deps and compiles; the final stage copies the artefact only.
- [ ] Final stage runs as a non-root user. **Verify:** `USER` directive present and not `root` / `0`.
- [ ] `WORKDIR` set explicitly; no operations relying on `/` or `/root`.
- [ ] `COPY` is used; `ADD` only for archive extraction or remote URLs (never as a general "smarter cp").
- [ ] Dependency-manifest files (`package.json`+`package-lock.json`/`bun.lockb`, `pyproject.toml`+`uv.lock` or `requirements.txt`) are copied and installed BEFORE the rest of the source so layer cache is preserved on code-only edits.
- [ ] Build-time dependencies (compilers, dev headers) are confined to the `builder` stage. The runtime stage does not contain `gcc`, `make`, `apt-get`, etc.
- [ ] No `apt-get update && apt-get install` without `--no-install-recommends` AND `rm -rf /var/lib/apt/lists/*` in the same `RUN`.
- [ ] No secrets baked into the image (no `ENV API_KEY=...`, no `COPY .env ...`). Build args are used only for non-secret values.

### 5. Dockerfile: image surface

- [ ] Base image is a slim/alpine variant for runtime where the language ecosystem supports it (e.g. `python:3.12-slim`, `node:20-slim`). Switching from slim → full requires a comment explaining why.
- [ ] `EXPOSE` documents the container's listening port; it does NOT publish.
- [ ] `CMD` is the exec form (`CMD ["python", "-m", "..."]`), not shell form, to receive signals correctly.
- [ ] Container-level healthcheck is set in compose, not in Dockerfile (single source of truth).

### 6. .dockerignore

- [ ] Each service has a `.dockerignore` next to its Dockerfile (or the root has one covering both).
- [ ] At minimum excludes: `.git`, `node_modules`, `__pycache__`, `.venv`, `.next`, `dist`, `build`, `coverage`, `.env*`, `*.log`, IDE config dirs.
- [ ] Excluding `.env*` is mandatory — a literal `.env` ending up in the image is a CRITICAL leak risk.

### 7. Build context size

- [ ] The build context is the service's own subtree (`./frontend` for the frontend service, `./backend` for the backend service) — not the repository root. Confirm by reading the compose `build.context:` value.
- [ ] No service-A code is copied into service-B's image.

### 8. Health & latency cross-checks

- [ ] Backend `/health` healthcheck verifies `postgres` and `llm` reachability (per BE-001/BE-003); not just a TCP-port probe on the backend itself.
- [ ] `llm` healthcheck waits for Ollama to have the `gemma4:e4b` model pulled / loadable; without that, the system passes G0 but fails the first real request.
- [ ] First-boot cold start does not exceed the 120 s budget. If the model pull is the bottleneck, the runbook (`docs/runbook-local-dev.md`) MUST call it out; otherwise it is a G0 failure.

### 9. Logging & resource hygiene

- [ ] No `--log-driver=none` or container-level log suppression — operational logs are needed for debugging.
- [ ] Application logs go to stdout/stderr (not a file inside the container) so compose / journald can collect them.
- [ ] Resource limits (`deploy.resources` or `mem_limit`) are set on services that can grow unbounded (notably `llm`) when the project has documented them. Absence is `[NOTE]`, not `[BLOCKER]`.

### 10. PHI rule cross-check (compose-specific)

- [ ] No hosted-LLM SDK installed inside any image. **Verify:** the cumulative `pip`/`npm` install list inside each Dockerfile does NOT include `openai`, `@anthropic-ai/sdk`, `@google/generative-ai`, `bedrock`, `cohere`, `replicate`, `langchain-openai`, etc.
- [ ] Backend image does not bake the prompt template or any sample PHI into the image (synthetic-only fixtures live in the test tree, not the runtime image).

## Anti-patterns to flag

- `:latest` tag on any pinned dependency.
- `USER root` (or absent `USER` so root is implicit) in the final stage.
- Single-stage build that ships compilers, dev headers, or full SDKs.
- `COPY . .` early in the Dockerfile (busts the dep-install cache).
- `ADD` used as a fancy `COPY` (use `COPY`; reserve `ADD` for archives/URLs).
- `apt-get install` without cleanup → bloats the image and ships the apt lists.
- `.env` (or any secret-bearing file) inside the build context with no `.dockerignore` entry.
- `ports: "5432:5432"` or `ports: "11434:11434"` on internal services.
- `extra_hosts` resolving to a public hostname or to `host.docker.internal` for the LLM hop.
- Bind mounts that overlay container binaries.
- `docker compose down -v` proposed in a runbook step.

## Verification commands (run via Bash from repo root)

```bash
# Internal-network rule (PHI §1 cross-check)
grep -nE '"5432:5432"|"11434:11434"' docker-compose.yml 2>/dev/null
grep -nE 'extra_hosts|host\.docker\.internal' docker-compose.yml 2>/dev/null

# Tag pinning
grep -nE 'image:\s+[^ ]+:latest' docker-compose.yml 2>/dev/null

# Healthcheck coverage
grep -nE 'healthcheck:' docker-compose.yml 2>/dev/null

# Non-root user in Dockerfiles
grep -RnE '^USER\s+' frontend/Dockerfile backend/Dockerfile 2>/dev/null

# Dockerignore coverage of secrets
test -f frontend/.dockerignore && grep -nE '\.env' frontend/.dockerignore 2>/dev/null
test -f backend/.dockerignore  && grep -nE '\.env' backend/.dockerignore  2>/dev/null

# Hosted-LLM SDKs sneaking into an image install layer
grep -RniE 'openai|anthropic|google-generativeai|bedrock|cohere|replicate|langchain-openai' frontend/Dockerfile backend/Dockerfile 2>/dev/null

# Compose-up sanity (G0)
docker compose ps --status running 2>/dev/null
```

## Output the Evaluator folds into its QA Block

Return one of:

- `docker-best-practices-master: PASS` — no findings.
- A bullet list of findings, each tagged `[BLOCKER]` / `[WARN]` / `[NOTE]`:
  - `[BLOCKER]` for any internal-port-published violation, `extra_hosts` to public IPs, hosted-LLM SDK baked into an image, root user in a final stage, secrets in build context, or G0 cold-start exceeding 120 s.
  - `[WARN]` for image bloat (build deps in runtime), missing `.dockerignore` entries that aren't secrets, missing healthchecks, missing resource limits where SPEC asks for them.
  - `[NOTE]` for layer-cache ordering, slim-base preferences, and runbook polish.

`[BLOCKER]` findings feed the Evaluator's `## QA Failure` Block under:

- **G4 (Security / PHI)** when the violation maps to `.claude/rules/local-llm-and-phi.md` §1.
- **G6 (Spec alignment)** when the violation maps to `SPEC.md#runtime-topology` Acceptance.
- **G0 (Compose-up)** when the cold-start budget or healthcheck is the failing axis.
- **G7 (Architecture)** otherwise.
