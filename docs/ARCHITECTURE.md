# LUCY — System Architecture

*As actually built (hackathon v1). Legend: ── live and verified · ┄┄ designed, wiring pending.*

## Big picture

```
                                  ┌─────────────────────────────────────────────┐
                                  │            USER'S MACHINE (local-first)      │
                                  │                                             │
  ┌──────────┐   IMAP (read-only) │  ┌──────────────────────────────────────┐   │
  │  GMAIL   │────────────────────┼─▶│           FastAPI  :8010             │   │
  │ (real    │   app password,    │  │  app/main.py                         │   │
  │  inbox)  │   All Mail,        │  │   /api/state  /api/tick  /api/approve│   │
  └────┬─────┘   incremental by   │  │   /api/gmail/*  /api/ingest (token)  │   │
       │         Message-ID       │  │   /api/sync (demo FALLBACK: 409 when │   │
       │                          │  │             real Gmail is connected) │   │
       │ raw records              │  └───────┬──────────────────┬───────────┘   │
       ▼ (mirror mode)            │          │                  │               │
  ┌──────────┐  Nexset  ┌──────┐  │  ┌───────▼───────┐   ┌──────▼──────────┐    │
  │  NEXLA   │┄detect┄▶│ REST │──┼─▶│  CPOS LOOP    │   │  Browser UI     │    │
  │ source   │          │ sink │  │  │  ENGINE       │   │ static/index.html│   │
  │ 125809   │          └──────┘  │  │ app/engine.py │   │  Mailbox·Tasks· │    │
  └──────────┘  (sink pending     │  │               │   │  Senders·Operator│   │
       ▲         real push URL)   │  │  ① Extractor  │   │  Auto-loop 2.5s │    │
       │                          │  │  ② Planner    │   │  Gmail sync 10s │    │
  cloudflared tunnel (verified:   │  │  ③ Executor   │   │  Approve/Reject │    │
  401 no token / 200 with token)  │  │  ④ Verifier   │   └─────────────────┘    │
                                  │  └───────┬───────┘                          │
                                  │          │ minimal prompts, structured JSON │
                                  │          ▼                                  │
                                  │   ┌─────────────┐     ┌──────────────────┐  │
                                  │   │ data/*.json │     │ app/tools.py     │  │
                                  │   │ state·creds │     │ tool registry    │  │
                                  │   │ (gitignored)│     │ (Zero.xyz seam)┄┄│  │
                                  │   └─────────────┘     └──────────────────┘  │
                                  └──────────┬──────────────────────────────────┘
                                             │ LLM calls (fallback: offline rules)
                                             ▼
                                   ┌───────────────────────┐
                                   │  AKASH (AkashML)      │  ── LIVE, verified:
                                   │  api.akashml.com      │  Chinese emails,
                                   │  Llama-3.3-70B        │  relative dates,
                                   │  stateless, JSON out  │  spam filtering
                                   └───────────────────────┘
```

## The loop (the product)

```
  EXTRACT ──▶ PLAN ──▶ [HUMAN APPROVES INTENT] ──▶ EXECUTE ──▶ VERIFY ──▶ closed
                ▲                                                 │
                └──────────── retry (auto-repair under the ───────┘
                              original approval's intent)
```

State machine (`app/models.py`): `open → awaiting_approval → in_progress →
awaiting_approval → verifying → closed`, with `verifying → retry → verifying`.
Approval is **per intent, not per attempt**: humans gate new intents; the loop
owns retries. Waiting is a valid planned action (planner returns None + audit line).

## Components

| Component | File(s) | Status |
|---|---|---|
| Loop engine + state machine | `app/engine.py`, `app/models.py` | live |
| ① Commitment Extractor (LLM-first, rule fallback, judgment cache) | `app/agents/extractor.py` | live |
| ② Planner (smallest useful action by deadline distance) | `app/agents/planner.py` | live |
| ③ Executor (acts only on approved intents) | `app/agents/executor.py` | live |
| ④ Outcome Verifier (checks reality; reopens loop) | `app/agents/verifier.py` | live |
| Gmail IMAP reader (read-only, incremental, All Mail) | `app/gmail.py` | live |
| Akash LLM client (SSL-verified, graceful fallback) | `app/llm.py` | live |
| Nexla push layer (mirror / primary routing) | `app/nexla.py` | live code; push URL pending from UI |
| Ingest webhook (token, fail-closed, validated) | `app/main.py /api/ingest` | live, verified from public internet |
| Tool registry (Zero.xyz provider seam) | `app/tools.py` | live local tools; Zero wiring pending docs |
| UI (Mailbox / Tasks / Senders / Operator) | `static/index.html` | live |
| Pomerium per-agent policy | `integrations/pomerium/policy.yaml` | designed |
| Akash SDL (self-hosted vLLM alternative) | `integrations/akash/deploy.yaml` | designed |

## Data flows

**Read (wide):** Gmail → IMAP fetch (only never-seen Message-IDs downloaded) →
parallel LLM judgment (cached forever) → every email visible in Mailbox with a
verdict → real commitments become task cards.

**Pipeline (Nexla):** same fetch → raw records pushed to Nexla source 125809 →
Nexset → REST sink → `/api/ingest` (token-guarded). Mirror mode by default —
message-ID dedupe makes double delivery harmless; `NEXLA_PRIMARY=1` makes Nexla
the sole ingest path. Local ingestion is the fallback, never the other way.

**Act (narrow):** planner proposal → human Approve → executor writes calendar
holds / outbox replies → verifier re-reads the outcome (thread ID + attachment)
→ closed, or retry with auto-repair.

## Trust boundaries

- **Credentials never leave the machine**: `data/gmail.json`, `data/llm.json`,
  `data/nexla_*.json`, `.env` — all gitignored, some chmod 600.
- **Inbound**: `/api/ingest` fail-closed (token required beyond loopback);
  payload schema validated (422); all email content HTML-escaped in the UI
  (stored-XSS hardened).
- **Outbound**: LLM gets minimal prompts, returns structured JSON, all output
  treated as untrusted (deterministic code owns state transitions); demo mock
  data cannot mix into live data (409 guard).
- **Production path** (per `docs/INTEGRATION_AUDIT.md`): this app becomes the
  read/propose plane beside CPOS2; the sole email send path stays CPOS2's
  `sendApprovedGmailDraft()` behind Pomerium and confirmation-token hashes.
```
