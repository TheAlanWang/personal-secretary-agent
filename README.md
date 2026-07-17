# LUCY — Personal Secretary Agent

> Other email assistants write your replies. **LUCY closes your loops**: she
> finds the commitments hidden in your email, tracks who owes what by when,
> takes the smallest useful action (with your approval), and **verifies the
> outcome actually happened** — repairing it herself when it didn't.

LUCY runs the **CPOS loop**: **C**ommitment · **P**erson · **O**utcome ·
**S**chedule — see [PRD.md](PRD.md).

**You approve intent, the loop handles attempts**: each new action needs your
one-time approval; failed outcomes are repaired automatically under that same
approval, and the loop advances itself (Auto Loop is on by default — use
*Tick Once* to narrate step by step).

## Quick start

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
# open http://localhost:8000
```

Zero API keys needed: V1 runs the four agents rule-based, with mock
inbox/outbox/calendar in `data/`. End-to-end check without the browser:

```bash
python3 smoke.py
```

**Real Gmail (optional):** use the *Gmail // connection* panel in the UI —
enable 2-Step Verification, create an [App Password](https://myaccount.google.com/apppasswords),
connect, then *Sync Gmail* pulls your latest inbox through the same extractor.
Credentials stay in `data/gmail.json` on your machine (gitignored).

## Demo script (~2 min)

1. **Sync Inbox** → the extractor turns the professor's email into a commitment
   card: *submit Phase 1 report, deadline 2026-07-23, in the same thread*.
2. The loop proposes *block 2 writing sessions* → **Approve** → calendar holds
   appear.
3. Set the simulated date to **2026-07-22** → the loop switches to *draft the
   submission reply with the report attached* → **Approve** → sent.
4. **The Loop 🔁 (hands off the keyboard)**: the verifier discovers the
   attachment is missing → card pulses red (`retry`) → the repair inherits your
   original approval, resends WITH the attachment, verifies — card turns green
   (`closed`) with no further clicks.
5. The audit trail shows exactly which agent did what, approved by whom.

## The four agents (`app/agents/`)

| Agent | Role |
|---|---|
| `extractor` | email → CommitmentRecord (promise, owner, deadline, expected outcome) |
| `planner` | picks the smallest useful action: block time / draft reply / resend / wait |
| `executor` | carries out **approved** actions only |
| `verifier` | checks reality vs expected outcome; failure reopens the loop |

## Sponsor integrations (`integrations/`)

| Sponsor | Role | Where |
|---|---|---|
| **Nexla** | ingests + normalizes email; delivers to our live `/api/ingest` webhook | `integrations/nexla/README.md` |
| **Pomerium** | per-agent least privilege; sending requires a human-approved request | `integrations/pomerium/policy.yaml` |
| **Akash** | private stateless LLM workers; `export LLM_BASE_URL=...` switches all agents from rules to LLM | `integrations/akash/deploy.yaml`, `app/llm.py` |

## Team workflow (hackathon)

Push straight to `main`, `git pull --rebase` before you start. Ownership:
`app/` (engine) · `static/` + `data/` (UI & demo data) · `integrations/` +
`README.md` + slides (story). The API contract is the five endpoints in
`app/main.py` — change those only after telling the team.
