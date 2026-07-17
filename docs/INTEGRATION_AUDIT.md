# INTEGRATION AUDIT — CPOS2 × Personal Secretary Agent (LUCY)

**Segment 1 deliverable.** CPOS2 (`Cparekh1208/CPOS2`, Nuxt 4 monorepo) is canonical.
Personal Secretary Agent (`TheAlanWang/personal-secretary-agent`, Python/FastAPI hackathon
build, "LUCY") is a behavioral reference only. No code was modified for this audit.

---

## 1. CPOS2 Gmail read paths

All Gmail I/O lives in `packages/gmail/src/`:

| File | Role |
|---|---|
| `oauth.ts` | Google OAuth flow; tokens AES-256-GCM encrypted (`@cpos/core`), stored in `oauth_tokens` |
| `sync.ts` | Thread/message sync into `gmail_threads` / `gmail_messages` |
| `watch.ts` | Gmail Pub/Sub watch registration; state in `gmail_watch_state` |
| `threading.ts`, `browse.ts`, `client.ts` | Thread resolution, listing, API client |
| `mime.ts`, `emailHtml.ts`, `sanitizeHtml.ts` | MIME build/parse, HTML sanitization |

Read-side Nitro routes: `apps/web/server/api/gmail/sync.post.ts`, `threads.get.ts`,
`thread/[id].get.ts`, `drafts.get.ts`, `watch/renew.post.ts`; push ingestion via
`apps/web/server/api/webhooks/gmail-pubsub.post.ts`; follow-up scan via
`apps/web/server/api/cron/followups.get.ts`.

## 2. The sole production send path

**One function sends email:** `sendApprovedGmailDraft()` in
`apps/web/server/utils/appGmailSend.ts` — its doc comment states it is "The ONLY function
in this codebase that calls Gmail's send API" and names its three legal callers:
`POST /api/gmail/draft/:id/send`, `POST /api/approval-queue/:id/send`,
`POST /api/composer/send-approved`.

Guard chain observed in `apps/web/server/api/gmail/draft/[id]/send.post.ts` +
`apps/web/server/utils/appSendConfirmation.ts`:

1. Rate limit (20/min), authenticated session, draft ownership (`requireOwnedAccount`).
2. `body.confirm === true` (Zod literal) — agents cannot reach this endpoint.
3. `validateApprovalSend()` from `@cpos/email-engine` (draft status verdict).
4. **Single-use confirmation token** (from `prepare-send.post.ts`, 5-minute TTL,
   `send_confirmation_tokens` table) binding SHA-256 hashes of recipient, subject, body,
   and attachments — any post-review edit invalidates it (`hashSendField`, NFKC-normalized).
5. `rejectSecretsInDraft()` content check; failures write `send_blocked` to `audit_log`.
6. Correct same-thread reply via persisted `gmailThreadIdRaw` fallback logic.

Invariant `ALLOW_AUTO_SEND=false` (env, `packages/config`) is permanent per `AGENTS.md`.
**Segment 8's "before sending" hash list is already ~80% implemented here** — missing
pieces are only thread-ID hash, current-state hash, and post-send retrieval verification.

## 3. Approval and policy mechanisms

- `approval_queue_items` (status: `pending|approved|denied|edited|sent|archived`;
  itemType: `email_draft|reminder|memory_proposal|protocol_update`), routes under
  `apps/web/server/api/approval-queue/`.
- Draft lifecycle `proposed|edited|saved_to_gmail|sent|discarded` on `gmail_drafts`.
- Deterministic policy validator in `@cpos/llm` / `@cpos/email-engine`; deterministic
  decisions beat model output (docs/SYSTEM_DESIGN.md §4.1.3).
- Every LLM pass persisted to `agent_runs` (+`agent_run_inputs/outputs`) and
  `draft_iterations` (role: `generator|critic|reviser|policy_validator|selector`).
- `audit_log` records send/block events. CSRF middleware + `production-guard.ts` plugin.
- Security test suite: `tests/security/` (~35 adversarial vitest files) +
  `scripts/security/*.mjs` gate wired into `.github/workflows/ci.yml`.

## 4. Database

Drizzle ORM on Neon Postgres (`packages/db/src/schema/index.ts`), **97 tables**. Groups
relevant to integration: Gmail (`gmail_threads/messages/drafts`, `send_confirmation_tokens`,
`gmail_watch_state`, caches/previews), approval (`approval_queue_items`,
`approval_item_attachments`), agents (`agent_runs*`, `agent_workflow_runs/checkpoints/events`,
`draft_iterations`, `email_workflows`, `email_generation_jobs`), models (`model_registry`,
`model_routing_policies`), memory (13 `memory_*` tables + `nodes`/`edges`), follow-ups
(`followup_*`, `reminders`, `sent_email_analytics`, `sent_email_response_events`), people
(`contacts`, `contact_records`, groups), plus auth/session/audit tables.

**There is no `commitment` concept anywhere in CPOS2** (grep across .ts/.md: zero hits).
The Segment 2 tables (commitments, loop instances, observations, plans, actions,
approvals, verification results, user interaction signals) are net-new.

## 5. Model router and structured output

`packages/llm/src/`: NVIDIA NIM OpenAI-compatible client (`client.ts`), provider resolution
(`providers.ts` — default `meta/llama-3.3-70b-instruct`, base
`https://integrate.api.nvidia.com/v1`, dual API keys `NVIDIA_NIM_API_KEY[_2]`, plus
embedding/rerank/vision model envs), structured generation (`structuredGenerate.ts`) with
**Zod-validated guided JSON** (`schema.ts`), deterministic policy validator. DB-side routing
via `model_registry` + `model_routing_policies`. Loop role strategy `generator_critic` on
`email_workflows.selectedModelStrategy`.

## 6. MCP packages

`packages/mcp-server` (stdio, run standalone via `pnpm mcp`, NOT deployed inside Nuxt).
`handlers.ts` is DB-backed, **read + propose only**: `searchThreads`, `getThreadContext`,
draft/reminder writes land as proposals for in-app review; the header comment states
"nothing here can send email (approval-first — see request_approved_send)".
`tests/security/mcp-security.test.ts` covers it.

## 7. Mocks and seeded runtime paths

- `workers/graphiti/mock-server.mjs` — local mock server (only content of `workers/`).
- `.claude/skills/run-cp-email-agent/mock-nim-email-engine.mjs` — dev-skill mock NIM.
- MOCK/DEMO string hits in runtime code: `apps/web/server/api/mail/accounts.get.ts`,
  `apps/web/app/pages/composer.vue` (verify and strip in Segment 10).
- QStash stub provider runs job handlers inline in dev (`packages/jobs`, AGENTS.md).

## 8. Neo4j dependencies

`packages/memgraph` (EmailMessage/Person/Company/Draft graph), `packages/memory-layer`,
`packages/graph`; `neo4j:5-community` in `infra/docker-compose.yml`; Neo4j Aura optional in
prod. **Already optional by design: no-ops when `NEO4J_URI` unset** (DEPLOY.md). Plan
compliance ("do not use Neo4j"): the new Python backend uses PostgreSQL(+pgvector) only;
CPOS2's optional graph remains untouched and disabled-by-default. No hard removal needed.

## 9. Personal Secretary (LUCY) behavior worth porting

Reference files in `personal-secretary-agent/`:

1. **Commitment as a first-class entity** (`app/models.py::new_record`): promise, owner,
   counterparty, deadline, expected_outcome, per-commitment audit history. CPOS2 tracks
   drafts/workflows but never *what was promised and whether reality matched*.
2. **Durable per-commitment loop state machine** (`app/engine.py::tick`):
   plan → approve → execute → verify → retry; maps onto Segment 5's larger enum.
3. **Outcome Verifier that checks reality after action** (`app/agents/verifier.py`):
   re-reads the sent thread, asserts thread-ID match + attachment presence, and *reopens
   the loop* on mismatch. CPOS2 verifies content **before** send (token hashes) but nothing
   verifies **after** send — the biggest behavioral gap; maps to Segment 8's post-send
   verification.
4. **"Waiting" as a legitimate planned action** (`app/agents/planner.py` returns None with
   an audit line) — matches Segment 5's requirement verbatim.
5. **Smallest-useful-action planning** keyed on deadline distance (block time now,
   draft near deadline).
6. **User interaction signals → operator profile** (`static/index.html::renderProfile`:
   approvals/rejections/slip counts, progressive insights) — the seed of Segment 9's
   preference learner, currently frontend-derived; port as `user_interaction_signals` rows.
7. **LLM extractor contract** (`app/agents/extractor.py`): strict JSON
   {commitment,promise,deadline,expected_outcome}, relative-date resolution against a
   reference date, spam/notification refusal, deterministic fallback — good starting prompt
   for Segment 4's joint extraction (add facts/requests/decisions/questions/confidence).

## 10. LUCY behavior that CONFLICTS with CPOS2 safety

| LUCY behavior | File | Conflict | Resolution |
|---|---|---|---|
| Auto-repair resend "inherits the user's original approval" | `app/engine.py` (tick, `was_retry` branch) | Violates "Never auto-send repair messages" and `ALLOW_AUTO_SEND=false` | Repair produces a **new approval_queue_item**; never auto-executes |
| Approve button → immediate execution, no content-bound token | `static/index.html` → `/api/approve/{id}` | Bypasses prepare-send confirmation-token binding | All executions route through CPOS2 prepare-send/consume-token flow |
| IMAP + app-password Gmail read (`app/gmail.py`), creds in `data/gmail.json` | Parallel, weaker credential path vs OAuth + AES-GCM | **Deprecate entirely**; Nexla (Segment 3) + CPOS2 OAuth are the only read paths |
| Mock outbox/calendar as runtime behavior (`app/agents/executor.py`, `store.py`) | Seeded runtime paths forbidden by Segment 10 | Do not port; test doubles only |
| `inject_failure` demo trap in executor | Deliberate runtime fault injection | Keep only as a pytest fixture |
| Relaxed-TLS history in `app/llm.py` (now CA-bundle chain) | CPOS2 security gate would flag | Python backend must pin verified TLS + explicit CA config |

## 11. File disposition map

**CPOS2 — reuse as-is (canonical, do not fork):** `packages/gmail/*`,
`apps/web/server/utils/appGmailSend.ts`, `appSendConfirmation.ts`, all
`api/gmail/*` + `api/approval-queue/*` routes, `packages/llm/*`, `packages/db/*`,
`packages/config`, `packages/core`, `packages/jobs`, `packages/mcp-server`,
`tests/security/*`, `scripts/security/*`.

**CPOS2 — adapt:** `packages/db` (new tables live in a separate `secretary` Postgres schema
owned by the Python service's Alembic — never let two ORMs own one table);
`apps/web/server/api/webhooks/` (add signed Nexla receiver OR host it in the Python
backend); approval-queue UI (surface commitment-loop items).

**LUCY — port concepts, rewrite code:** `app/models.py`, `app/engine.py`,
`app/agents/{extractor,planner,verifier}.py` → `services/secretary-backend` (Segments 2/5)
with the Segment 5 state machine and Postgres locking.

**LUCY — deprecate / do not port:** `app/gmail.py` (IMAP path), `app/agents/executor.py`
mock sends, `app/tools.py` Zero seam (superseded by Segment 10 official connector),
`smoke.py` demo flow, `static/index.html` (CPOS2's Nuxt app is the UI), `integrations/*`
(illustrative stubs superseded by real Segment 3/6/7 work).

## 12. Selected strategy: one email send path

**The Python backend never touches Gmail send and never holds send-capable credentials.**

```
Nexla → secretary-backend (ingest, extract, plan, verify)      [read/propose plane]
secretary-backend → CPOS2 approval-queue item + prepared draft [proposal handoff]
Human approves in CPOS2 UI → prepare-send token → sendApprovedGmailDraft()  [sole send]
secretary-backend Outcome Verifier reads the sent thread → closes/reopens loop
```

Concretely: the Segment 5 "Action Preparer" calls CPOS2's authenticated API to create
`gmail_drafts` + `approval_queue_items`; Segment 8 extends `send_confirmation_tokens`
with thread-ID and current-state hashes and adds a post-send verification job. Repairs
(LUCY's retry) become new queue items requiring fresh human approval.

## 13. Risks of introducing a Python backend

1. **Schema ownership drift** — Drizzle (TS) and Alembic (Py) on one database. Mitigation:
   dedicated `secretary` schema owned solely by Alembic; cross-references by Gmail
   message/thread IDs + content hashes, not foreign keys into Drizzle tables.
2. **Two runtimes, two lifecycles** — Vercel serverless (bursty, stateless) vs Akash
   long-running workers. Mitigation: all cross-calls through Pomerium-verified service
   identities (Segment 7); no shared in-process state; queue-mediated only.
3. **Duplicate Gmail surface** — any Python google-api client is a standing temptation to
   send. Mitigation: Python Google credentials scoped `gmail.readonly` at the OAuth consent
   level, enforced again by Pomerium route policy, asserted by adversarial tests (Segment 7).
4. **Ingestion race/duplication** — Nexla webhook and CPOS2's own Pub/Sub sync both see the
   same mail. Mitigation: idempotency on RFC-822 Message-ID + content hash (Segment 3);
   one designated writer per table group.
5. **Security-gate asymmetry** — CPOS2's CI security gate doesn't scan Python. Mitigation:
   mirror it (ruff + bandit + secret-pattern check) in `services/secretary-backend` CI
   before first merge.
6. **Config/secret sprawl** — two env systems. Mitigation: Pydantic settings mirroring
   `packages/config`'s public/secret classification; single source in deploy env.

## 14. Implementation order

1. **Segment 2** — `services/secretary-backend` skeleton + Alembic migrations for the 14
   net-new tables (own `secretary` schema); CI parity with CPOS2's security gate.
2. **Segment 3** — Nexla ingestion → secretary-backend webhook (signed, idempotent);
   provenance + content hashes; read-only Nexla MCP tools.
3. **Segment 4** — deterministic MIME parser + incremental thread state + joint extraction
   schema (seed prompts from LUCY's extractor contract).
4. **Segment 5** — six bounded agents + full state machine; port LUCY's verifier/waiting
   semantics; Postgres row locking + idempotency keys.
5. **Segment 8, pulled forward before infra** — proposal handoff into CPOS2's approval
   queue + `send_confirmation_tokens` extensions (thread-ID hash, current-state hash) +
   post-send verification job. This is the integration seam; proving it early de-risks
   everything else. *(Needs a CPOS2-side PR — smallest possible diff.)*
6. **Segment 6** — Akash SDLs (FastAPI, workers, scheduler, Postgres+pgvector, Redis,
   MinIO, Pomerium, LLM server) + model benchmarks (small extractor vs stronger planner;
   baseline = the NIM-hosted `llama-3.3-70b` CPOS2 already uses).
7. **Segment 7** — Pomerium per-agent identities + route policies; adversarial authz tests.
8. **Segment 9** — preference learner over `user_interaction_signals` (approval-gated
   atomic candidate preferences; decay/scope/rollback).
9. **Segment 10** — Zero connector (allowlist, cost caps), strip CPOS2 runtime mocks
   (`workers/graphiti/mock-server.mjs`, `api/mail/accounts.get.ts` MOCK branch), full test
   matrix, final docs and honest status report.
