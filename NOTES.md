# NOTES.md — ADR Index

This file is the index of architecture decisions for the project. Decision records themselves live in `docs/adr/` and follow `docs/adr/0000-template.md`.

## How to add an ADR

1. Copy `docs/adr/0000-template.md` to `docs/adr/<NNNN>-<kebab-title>.md` using the next free 4-digit number.
2. Fill in Context, Decision, Consequences, Alternatives, Gates affected, Open follow-ups.
3. Set Status to `Proposed`. Planner promotes to `Accepted` after review.
4. Add a row to the index below in chronological order.
5. Reference the ADR from the SPEC Block it governs (e.g. `docs/adr/0007-...md`).

## Status values

- `Proposed` — under discussion, not yet binding.
- `Accepted` — binding; agents must obey.
- `Superseded by ADR-NNNN` — historical only; new ADR is binding.
- `Deprecated` — no longer applicable; do not follow.

## Index

| ID                                                     | Title                                                           | Status   | Date       |
| ------------------------------------------------------ | --------------------------------------------------------------- | -------- | ---------- |
| [ADR-0001](docs/adr/0001-voice-input-and-local-asr.md) | Voice input and local ASR service                               | Accepted | 2026-05-12 |
| [ADR-0003](docs/adr/0003-streaming-asr-chunked.md)     | Chunked streaming ASR with env-var rollback                     | Accepted | 2026-05-12 |
| [ADR-0004](docs/adr/0004-phi-in-react-state.md)        | PHI buffers MUST live in useRef, not useState                   | Proposed | 2026-05-12 |
| [ADR-0005](docs/adr/0005-agent-push-and-pr-policy.md)  | Agents may push to non-default branches and open PRs (no merge) | Accepted | 2026-05-12 |
