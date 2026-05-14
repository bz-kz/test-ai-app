---
name: cost-check
description: Verify latency, RAM, and model-tier budgets for inference-touching changes against `SPEC.md#hardware-assumptions`. Owns G5. Token billing is NOT in scope (the model is local). Use when a Block has `Inference Impact: yes` or whenever a change affects the inference pipeline / latency tier / model variant.
---

# cost-check

**Project rule this skill enforces:** `SPEC.md#hardware-assumptions` + `SPEC.md#inference-layer-contract` (LLM) + `SPEC.md#asr-layer-contract` (ASR) — the local Docker stack must stay within the pinned latency and RAM envelopes for `gemma4:e4b` + `whisper.cpp medium-q5_0`.

This skill replaces the legacy `cost-check` subagent. It is a recipe: caller has Bash + Read, walks the threshold checklist below, captures observed numbers via `docker stats` / log inspection / config grep, and returns a structured findings report. "Cost" here is **latency** and **RAM**, not token billing.

## When to use

- Generator self-evals **before** handing off to Evaluator on any Block where `Inference Impact: yes`.
- Evaluator re-runs the same checklist during QA on the same Block class.
- Main loop runs it ad-hoc when a config bump touches `LLM_*` / `ASR_*` env vars, model variants, or hardware-assumption sections of SPEC.md.

## Focus areas (severity priors)

1. **Model singularity.** The project pins `gemma4:e4b` (LLM) and `whisper.cpp medium-q5_0` (ASR). Introducing a different model variant without an ADR is **CRITICAL**.
2. **Latency budget — LLM.** First-token p95 ≤1 s and total-response p95 ≤6 s for 1k output tokens on the reference dev hardware per `SPEC.md#hardware-assumptions`. **This is the aspirational GPU target.** On the CPU-only reference path the measured operating point is first-token ~2–3 min and total ~4–5 min (PR #13 / INF-006 Playwright reproduction 2026-05-13). The SPEC budget is unchanged; report CPU vs SPEC divergence as `[INFO]` with explicit "CPU operating point" framing, NOT as a regression. Closing the gap requires an ADR (GPU offload, hosted LLM, model swap, or quantization A/B). The configured timeout is `LLM_TIMEOUT_S=600` (PR #13, was `300` post-INF-003 / commit `fa04bae`, was `60` originally).
3. **Latency budget — ASR.** `ASR_TIMEOUT_S=90` covers RTF ≤1.5× of a 60 s clip on reference CPU. First-byte does not apply (non-streaming). Hard cap on audio: 60 s, ≤2 MB payload, mono.
4. **RAM peak.**
   - `gemma4:e4b` loaded: ~10 GiB resident (INF-003).
   - `whisper.cpp medium-q5_0`: ~0.7–0.9 GiB resident at idle, ~1 GiB peak during transcription.
   - Co-resident envelope on Docker Desktop: ≥13 GiB allocation (INF-004 / ADR-0001).
   - Anything above the envelope on the reference hardware is **CRITICAL** with a suggested mitigation (lower context length, trim prompt, ADR for variant change).
5. **Prompt economy.** Gemma 4 E4B is small; long system prompts disproportionately hurt latency. Suggest factoring shared instructions, summarising patient history before the prompt, and trimming verbose chain-of-thought scaffolds.
6. **Looping behaviour.** If the Generator is calling the model in a loop where one well-shaped prompt would do, flag it as a structural cost issue.
7. **New deps weight.** Frontend additions like `recordrtc`, `opus-recorder`, `lamejs`, etc. — flag as **WARNING** (the project prefers native browser APIs). A new heavy backend dep that loads at import time and grows the container RSS is **WARNING**.

## Verification commands

Run these via Bash and capture output. Compare each observed number against the threshold.

```bash
# Probe 1 — Model singularity (LLM + ASR)
grep -nE 'LLM_MODEL|ASR_MODEL' docker-compose.yml backend/app/infrastructure/llm/config.py backend/app/infrastructure/asr/config.py 2>/dev/null

# Probe 2 — Timeout consistency between SPEC, config, and runtime
grep -nE 'LLM_TIMEOUT_S|ASR_TIMEOUT_S' docker-compose.yml backend/app/infrastructure/llm/config.py backend/app/infrastructure/asr/config.py SPEC.md frontend/SPEC.md

# Probe 3 — Co-resident RAM snapshot (requires services up)
docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}'

# Probe 4 — Docker Desktop memory allocation
docker info --format 'MemTotal: {{.MemTotal}}'

# Probe 5 — Frontend dep additions (audio / streaming libraries)
grep -E '"(recordrtc|audio-recorder-polyfill|opus-recorder|extendable-media-recorder|lamejs)"' frontend/package.json && exit 1 || echo "clean"

# Probe 6 — Audio payload caps
grep -nE 'AUDIO_MAX_BYTES|AUDIO_MAX_DURATION_S|_MAX_AUDIO_BYTES' frontend/src backend/app -r

# Probe 7 — Latency UX tier constants reference
grep -nE 'ASR_LATENCY_(SPINNER|HINT|CANCEL)_MS|LATENCY_(SPINNER|SKELETON|HINT|CANCEL)_MS' frontend/src -r

# Probe 8 — Recent commits touching inference config (sanity scan for accidental drift)
git log --oneline -n 20 -- docker-compose.yml backend/app/infrastructure/
```

## Output format

```
## Cost Findings: <task-id>

- **Goal:** Report whether the inference budget is met and where to cut if not.
- **Inputs:** SPEC.md#hardware-assumptions; SPEC.md#inference-layer-contract; SPEC.md#asr-layer-contract; <Block path>; `docker stats` snapshot.
- **Acceptance:**
  - [ ] Latency p95 within budget (or static analysis vs timeout matches budget).
  - [ ] RAM peak within budget.
  - [ ] Model tier matches Spec (LLM_MODEL=gemma4:e4b; ASR_MODEL=ggml-medium-q5_0.bin).
- **Out-of-scope:** Token billing (no hosted LLM).
- **Open-questions:** _(none)_
- **Findings:**
  - [SEVERITY] <one-line summary> — observed: <number/condition>; threshold: <number>; suggested fix: <one line>.
- **Net verdict:** PASS | FAIL
```

If real recordings or real LLM calls are not yet available (e.g. for a frontend-only Block that ships before the wiring round-trips with a live model), state explicitly: "live p95 measurement deferred to <Block N>; static analysis verifies timeout matches the budget".

## When to escalate

If the Block's budgets cannot be met by `gemma4:e4b` (LLM) or `whisper.cpp medium-q5_0` (ASR) on the assumed hardware, return FAIL and ask Planner (via the requesting agent) to either lower the budget, trim scope, or open an ADR for a variant change. Do not silently approve a different model variant.

## Anti-patterns

- Talking about "tokens per dollar". The model is local; that frame is wrong here.
- Approving the largest model on the grounds of "best quality" without weighing latency and VRAM.
- Returning prose instead of the structured Findings shape — downstream agents cannot machine-check it.
- Quoting Generator's self-reported numbers without running `docker stats` independently.
- Reading `LLM_TIMEOUT_S=60` from a stale doc when `docker-compose.yml` says `600` — always grep the live config, not the SPEC narrative.
