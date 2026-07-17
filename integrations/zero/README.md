# Zero.xyz Integration — Token-Gated Extra Tools

**Status: integration seam live, sponsor API wiring pending.**

## Role in LUCY

The agents' core skill set is small on purpose. When the Planner needs a
capability outside it — find the right attachment, convert a document,
resolve a link — the call goes through a tool registry (`app/tools.py`)
instead of being hardcoded into an agent. Zero.xyz plugs in as a tool
provider there, and each call is **token-metered**: the agent spends tokens
only when a tool measurably advances a commitment, keeping autonomous tool
usage accountable.

## What is already wired

- `app/tools.py` — the registry. The Executor already resolves the report
  attachment via `tools.call("find_attachment", ...)` rather than a hardcoded
  path.
- Local fallback tools keep the demo fully offline; the Zero.xyz provider
  activates when `ZERO_API_KEY` is set and falls back gracefully on failure —
  the same resilience pattern as the Akash LLM workers.

## To finish (once sponsor docs are in hand)

1. Fill in `_zero_call()` in `app/tools.py` with the real endpoint + auth.
2. Map registry tool names to Zero.xyz tool identifiers.
3. Record per-call token spend into the commitment's audit history, so the
   trail shows what each tool call cost.
