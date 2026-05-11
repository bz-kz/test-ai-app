---
name: fastapi-python
description: Use during Evaluator G6/G7 review of any Block that introduces or modifies backend FastAPI / Python 3.12 / Pydantic v2 / SQLAlchemy 2.0 code. Checks typing rigor, DDD layer direction, dependency injection, async/sync correctness, exception handling, OpenAPI surface, and test patterns against backend/SPEC.md.
---

# fastapi-python

Evaluation checklist for FastAPI + Python 3.12 + Pydantic v2 + SQLAlchemy 2.0 (async) code in this project. The Evaluator invokes this skill when a Block's diff touches `backend/app/**` or `backend/main.py`. Findings feed G7 (Architecture) and G6 (Spec alignment); a PHI-related finding may also feed G4 if security-check missed it.

## Required reading

1. `backend/SPEC.md` — Backend Mission, Layer Boundaries, Inference Adapter, Persistence, API Surface.
2. `SPEC.md#inference-layer-contract` — `LocalLLMClient` contract.
3. `.claude/rules/local-llm-and-phi.md` — PHI in logs, inference-layer boundary, hosted-SDK ban.
4. The Block's `Reference SPEC` anchor and the diff under review.

## Project pins

- Python: 3.12+; from-future imports allowed.
- FastAPI: 0.110+; async by default; `response_model=` on every endpoint.
- Pydantic: v2; `model_config = ConfigDict(...)`; `Field(...)` for validation.
- SQLAlchemy: 2.0 async (`AsyncSession`, `select(...)`, `MappedColumn`).
- Type checker: `pyright` strict; no `# type: ignore` without an inline reason.
- Linter / formatter: `ruff` (single tool for both).
- Test runner: `pytest` (async via `pytest-asyncio` or `anyio`).
- Logger: `logging` module, project logger; never `print` in committed code.

## Checklist — each item maps to observable evidence

### 1. DDD layer direction (G7 cornerstone)

- [ ] `app/domain/` imports nothing from other `app.*` packages. **Verify:** `grep -RnE '^from app\.' backend/app/domain` returns 0 hits (except `from app.domain.*` re-exports).
- [ ] `app/usecases/` imports `app.domain.*` and `app.infrastructure.*` only — never `app.interfaces.*`. **Verify:** `grep -RnE '^from app\.interfaces' backend/app/usecases` returns 0 hits.
- [ ] `app/infrastructure/` imports `app.domain.*` only. **Verify:** `grep -RnE '^from app\.(usecases|interfaces)' backend/app/infrastructure` returns 0 hits.
- [ ] `app/interfaces/` imports `app.usecases.*` and `app.domain.*` only — never `app.infrastructure.*` directly. **Verify:** `grep -RnE '^from app\.infrastructure' backend/app/interfaces` returns 0 hits.
- [ ] Inference calls live ONLY inside `app/infrastructure/llm/`. **Verify:** `grep -RnE 'http://llm|ollama|httpx\.' backend/app | grep -v '^backend/app/infrastructure/llm/'` returns 0 hits. This is also `.claude/rules/local-llm-and-phi.md` §2.

### 2. Type rigor

- [ ] `pyright` reports 0 errors and 0 warnings.
- [ ] Public function signatures use concrete types — no bare `dict`, `list`, `tuple` without parameters.
- [ ] No `typing.Any` in public signatures. Use `object`, a `TypedDict`, a Pydantic model, or a `Protocol`.
- [ ] `# type: ignore[...]` carries the specific error code and an inline reason. **Verify:** `grep -RnE 'type:\s*ignore' backend/app | grep -vE '#\s*type:\s*ignore\[[a-z-]+\].+#'` — every hit should have both the code AND a reason.
- [ ] All cross-layer boundaries use Pydantic models or dataclasses, not raw dicts.

### 3. Pydantic v2

- [ ] Request/Response bodies are `BaseModel` subclasses; field constraints use `Field(...)` (min/max length, ge/le, pattern).
- [ ] `model_config = ConfigDict(extra='forbid')` on request models to reject unknown fields. (Response models default to closed via Pydantic v2's `model_dump` behaviour.)
- [ ] No `pydantic.v1` legacy imports.
- [ ] Validators use `@field_validator(...)` / `@model_validator(...)` — not the v1 `@validator` decorator.
- [ ] `datetime` fields are timezone-aware (UTC) at boundaries.

### 4. FastAPI surface

- [ ] Every endpoint declares `response_model=`. **Verify:** `grep -RnE '@(app|router)\.(get|post|put|patch|delete)\(' backend/app backend/main.py` — each match's nearby decorator block contains `response_model=` (or returns `Response`/`JSONResponse` deliberately).
- [ ] Errors normalised to `{ "code": str, "message": str }` (the `ErrorResponse` envelope from BE-003) for every non-2xx that surfaces to the client. Messages MUST NOT echo PHI.
- [ ] OpenAPI: `responses={404: {"model": ErrorResponse}, ...}` declared on endpoints that can return non-200 statuses so the schema documents them.
- [ ] Path parameters typed as `UUID` (not `str`) for entity identifiers.
- [ ] Query parameters use `Query(..., min_length=N)` for required string queries; default values do not silently allow empty input.
- [ ] No mutable default arguments (`Depends()` is the FastAPI canonical exception; `B008` is intentionally ignored in `pyproject.toml`).

### 5. Dependency injection

- [ ] Database sessions flow through a FastAPI dependency (e.g. `get_session`) — never constructed ad-hoc in a router.
- [ ] Routers depend on usecase callables, not on repositories or sessions directly. Repositories are constructed inside usecases or a usecase-layer DI factory (`app/usecases/di.py`).
- [ ] Tests override dependencies via `app.dependency_overrides[...]` — not by monkeypatching internals.

### 6. Async / sync

- [ ] `async def` for any handler that awaits I/O. Otherwise plain `def` is fine.
- [ ] No blocking I/O inside `async def`. **Verify:** ad-hoc `time.sleep`, `requests.*`, sync DB calls are absent.
- [ ] `AsyncSession` is the only session type in `app/infrastructure/db/` and downstream.
- [ ] `pytest.mark.asyncio` (or `pytest.mark.anyio`) decorates every async test that awaits a coroutine.

### 7. Logging & PHI

- [ ] Module-level `logger = logging.getLogger(__name__)`. No `print(`. **Verify:** `grep -RnE '^\s*print\(' backend/app` returns 0 hits.
- [ ] Any logger call that touches a request body, a prompt, a model response, or a PHI column value passes the value through `mask_phi` (from `app.domain.phi`). **Verify:** for every `logger.(info|warning|error|debug)\(.*(mrn|patient|encounter|prompt|content|name|dob)` in `backend/app`, the value is masked.
- [ ] Stack traces from inference exceptions use the masked-exception wrapper. The raw prompt does NOT appear in `__str__` or `__repr__`.
- [ ] Audit-log `meta_json` never contains PHI; it stores stable identifiers and codes only.

### 8. SQLAlchemy 2.0 (async)

- [ ] ORM models live in `app/infrastructure/db/models.py`. PHI columns are flagged via `MappedColumn(info={"phi": True})` (per BE-002).
- [ ] Queries use `select(...)` (2.0 style); no legacy `Session.query(...)`.
- [ ] Repository methods accept and return domain entities (not ORM rows). Mappers do the translation.
- [ ] `record_final` immutability is enforced both at the model level (the `before_flush` event from BE-002) AND at the repository level (no `update_*` method).
- [ ] Transactions commit/rollback at the usecase boundary — not inside repositories.

### 9. Exception handling

- [ ] Domain / usecase errors are typed exception classes (e.g., `MRNConflict`, `InferenceError`). Routers translate them to `HTTPException(status_code=..., detail={"code": ..., "message": ...})` — never to raw string detail.
- [ ] Uncaught exceptions are handled by `app/interfaces/exception_handlers.py` (the 500 handler from BE-003). The handler MUST NOT echo request body in the response or in the log.
- [ ] `InferenceError` scrubs the prompt before logging.

### 10. Tests

- [ ] Unit tests use `FakeLocalLLMClient` for inference. Real Gemma is exercised only behind `pytest -m integration`.
- [ ] Repository tests use a transactional fixture (in-memory SQLite or rolled-back postgres) — not a real persistent DB.
- [ ] Router tests use FastAPI `TestClient` with `app.dependency_overrides` for usecase factories.
- [ ] Every new endpoint has at least one test for each declared response status (200, 4xx, 5xx where applicable).
- [ ] PHI fixtures are synthetic; no real PHI in the repo.

### 11. Hosted-LLM ban (PHI rule §1)

- [ ] No hosted-LLM SDK in `backend/requirements.txt` or `backend/pyproject.toml`. **Verify:** `grep -Ei 'openai|anthropic|google-generativeai|bedrock|cohere|replicate|langchain-openai' backend/requirements.txt backend/pyproject.toml` returns 0 hits.

## Anti-patterns to flag

- `dict[str, Any]` flowing into a router from external input.
- `print(` in committed code.
- `requests.*` (sync HTTP) anywhere in an async path.
- Raw SQL strings in usecases or interfaces (must live in repositories).
- `Session.query(...)` (SQLAlchemy 1.x style) — should be `select(...)`.
- A router calling a repository directly (G7 violation per the BE-004 lesson).
- Catching `Exception` broadly and re-raising as `HTTPException(500, detail=str(e))` — leaks PHI; use the global 500 handler.
- Constructing `OllamaLocalLLMClient()` per request inside a router (cost-check smell; use FastAPI Depends + singleton).
- `# type: ignore` without a specific error code and an inline reason.
- A migration that creates a PHI column without the `phi=True` info marker.

## Verification commands (run via Bash from repo root)

```bash
# Layer direction (G7)
grep -RnE '^from app\.' backend/app/domain 2>/dev/null
grep -RnE '^from app\.interfaces' backend/app/usecases 2>/dev/null
grep -RnE '^from app\.(usecases|interfaces)' backend/app/infrastructure 2>/dev/null
grep -RnE '^from app\.infrastructure' backend/app/interfaces 2>/dev/null

# Inference boundary (G4 cross-check)
grep -RnE 'http://llm|ollama|httpx\.' backend/app 2>/dev/null | grep -v '^backend/app/infrastructure/llm/'

# Hosted-LLM SDKs (G4)
grep -Ei 'openai|anthropic|google-generativeai|bedrock|cohere|replicate|langchain-openai' backend/requirements.txt backend/pyproject.toml 2>/dev/null

# Print statements
grep -RnE '^\s*print\(' backend/app 2>/dev/null

# Bare type: ignore
grep -RnE 'type:\s*ignore' backend/app 2>/dev/null

# Pydantic v1 legacy
grep -RnE 'from pydantic\.v1' backend/app 2>/dev/null

# response_model coverage
grep -RnE '@(app|router)\.(get|post|put|patch|delete)\(' backend/app backend/main.py 2>/dev/null
```

## Output the Evaluator folds into its QA Block

Return one of:

- `fastapi-python: PASS` — no findings.
- A bullet list of findings, each tagged `[BLOCKER]` / `[WARN]` / `[NOTE]`:
  - `[BLOCKER]` for any layer-direction violation, hosted-LLM SDK presence, inference call outside `app/infrastructure/llm/`, PHI in a logger call, `print(`, missing `response_model=` on an endpoint, or a raw `dict` flowing across a layer boundary.
  - `[WARN]` for missing `responses=` OpenAPI annotations, missing `Field` constraints on request models, mutable default arguments, or per-request construction of expensive clients.
  - `[NOTE]` for style suggestions (async/sync micro-optimisations, additional test coverage).

`[BLOCKER]` findings feed the Evaluator's `## QA Failure` Block under G7 (Architecture) — or G6 (Spec alignment) when a specific `backend/SPEC.md` Acceptance bullet is the violated rule, or G4 (Security) when the violation maps to `.claude/rules/local-llm-and-phi.md`.
