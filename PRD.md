# PRD — CPOS Loop: A Personal Secretary Agent

**Hackathon MVP · v0.1 · 2026-07-17**

---

## 1. Overview

CPOS Loop is a **local-first communication system** that finds real commitments hidden inside emails, calendar events, and documents. Instead of just summarizing messages or drafting replies, it tracks the full lifecycle of a commitment:

- **C**ommitment — what was promised
- **P**erson/Owner — who owns the next step
- **O**utcome — what result is expected
- **S**chedule — what the deadline is

It then helps with the **smallest useful action** (drafting a reply, blocking time, finding an attachment, or deliberately waiting), verifies what actually happened, and **loops** — if the outcome is incomplete or wrong, it re-plans and tries again.

Personal data stays on the user's machine. Any outward action (sending email, changing calendar) requires explicit user approval.

## 2. Problem

Email assistants today summarize and reply, but they don't **close loops**. Real productivity failures are not "too much email" — they are broken commitments: a promise made in a thread three weeks ago, with a deadline nobody is tracking and an expected outcome nobody verifies. Humans are bad at this bookkeeping; LLMs are good at extraction but need structure, permissions, and follow-through.

## 3. Running Example (Demo Scenario)

> **Situation:** A conversation with a professor about your research.
> **Promise:** Submit the Phase 1 report.
> **Owner:** You (the user).
> **Next steps:** Phase 1 preliminary research → Phase 2 implementation → …
> **Deadline:** Next Thursday (July 23, 2026).
> **Expected outcome:** Report submitted **in the same email thread**.

CPOS Loop extracts this commitment from the thread, blocks writing time on the calendar, tracks progress, drafts the submission reply with the report attached, and after sending, verifies the report actually landed in the correct thread before marking the loop closed.

## 4. Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    User's Machine (local-first)          │
│                                                          │
│  Email / Calendar / Docs                                 │
│        │                                                 │
│        ▼                                                 │
│  [ NEXLA ]  ingest + normalize into CommitmentRecords    │
│        │                                                 │
│        ▼                                                 │
│  ┌────────────── CPOS Agent Loop ──────────────┐         │
│  │ ① Extractor → ② Planner → ③ Executor        │         │
│  │        ▲                        │            │         │
│  │        └──── ④ Verifier ◄───────┘  (loop)    │         │
│  └──────────────────────────────────────────────┘        │
│        │                                                 │
│  [ POMERIUM ]                                            │
│  per-agent authZ, approval gates, audit log              │
└────────┼─────────────────────────────────────────────────┘
         ▼
   [ AKASH ]  private stateless LLM inference workers (GPU)
   (only anonymized/minimal prompts leave the machine)
```

## 5. AI Agents (4)

| # | Agent | Role | Input → Output |
|---|-------|------|----------------|
| 1 | **Commitment Extractor** | Reads normalized messages and finds commitments: promise, owner, deadline, expected outcome. | Nexla-normalized records → `CommitmentRecord` |
| 2 | **Planner** | Decides the *smallest useful next action*: reply, block time, find attachment, or wait. | `CommitmentRecord` + state → `ActionPlan` |
| 3 | **Executor** | Prepares the action (draft reply, calendar hold, attachment lookup). Never sends/changes anything without user approval via Pomerium gate. | `ActionPlan` → prepared action + approval request |
| 4 | **Outcome Verifier** | After execution, checks what actually happened (did the reply land in the right thread? was the report attached?). If incomplete/failed/wrong → re-opens the loop and feeds the Planner. | executed action + new data → `verified / retry / escalate` |

All agent inference runs as **stateless workers on Akash**; agent state (commitments, plans, history) stays local.

## 6. Sponsor Technology Integration

### Nexla — Data
- Ingests and **normalizes** email, calendar events, and documents into a single record schema (`CommitmentRecord` candidates).
- Handles the messy part: threading, deduplication, attachment metadata, incremental sync.
- Output feeds the Commitment Extractor agent.

### Pomerium — Auth
- **Per-agent, least-privilege access policy**: the Extractor can read mail but never send; the Executor can draft but sending requires an approval-gated route.
- Every outward action (send email, modify calendar) passes through a Pomerium policy check + explicit user approval.
- Gives an auditable log of "which agent did what, with whose approval."

### Akash — GPU & Tokens
- Runs the **private, stateless LLM inference workers** for all four agents on decentralized GPU.
- Stateless by design: workers receive minimal prompts, return structured output, retain nothing — consistent with local-first privacy.
- Token-metered compute keeps cost transparent per loop iteration.

## 7. Core Data Model

```json
CommitmentRecord {
  "id": "cpos-001",
  "source_thread": "email:prof-research-thread",
  "promise": "Submit Phase 1 report",
  "owner": "user",
  "counterparty": "professor",
  "deadline": "2026-07-23",
  "expected_outcome": "report attached as reply in the same thread",
  "phases": ["Phase 1: preliminary research", "Phase 2: implementation"],
  "status": "open | in_progress | awaiting_approval | verifying | closed | retry"
}
```

## 8. User Flow (MVP)

1. Nexla syncs the professor's email thread → Extractor creates `cpos-001`.
2. Planner: deadline is 6 days out → smallest action = **block 2 writing sessions** on calendar → user approves (Pomerium gate).
3. As the deadline nears, Planner switches to: **draft reply in the same thread + attach report** → Executor prepares the draft.
4. User approves → email sent.
5. Verifier confirms: correct thread ✓, attachment present ✓ → loop **closed**. If the attachment was missing, status → `retry`, Planner re-plans.

## 9. MVP Scope (Hackathon)

**In scope:** one email account, the demo scenario end-to-end, all four agents, all three sponsor integrations (Nexla, Pomerium, Akash), CLI/simple web UI, approval prompt.
**Out of scope:** multi-user, mobile, non-email channels, automatic sending without approval, fine-tuned models.

## 10. Success Criteria (Demo)

- [ ] Commitment auto-extracted from a real email thread with correct deadline (2026-07-23) and expected outcome.
- [ ] Calendar block proposed and created only after approval.
- [ ] Reply drafted **in the same thread** with attachment.
- [ ] Verifier catches an injected failure (missing attachment) and re-plans — the "loop" moment.
- [ ] Pomerium audit log shows per-agent permissions; Akash dashboard shows stateless inference; Nexla shows the normalization pipeline.
