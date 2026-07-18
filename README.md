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

1. Connect Gmail (top right), have "the professor" send the ask **with a
   deadline in the next 2 days** — within seconds the extractor turns the real
   email into a commitment card. (Offline fallback:
   `curl -X POST localhost:8010/api/sync` loads a demo email — refused while
   Gmail is connected, so sample data never mixes into live data.)
2. The clock is real: with a near deadline the loop goes straight to *draft
   the submission reply with the report attached* → **Approve** → sent. (A
   farther deadline gets *block writing sessions* first — the planner always
   picks the smallest useful action.)
3. **The Loop 🔁 (hands off the keyboard)**: the verifier discovers the
   attachment is missing → card pulses red (`retry`) → the repair inherits your
   original approval, resends WITH the attachment, verifies — card turns green
   (`closed`) with no further clicks.
4. The audit trail shows exactly which agent did what, approved by whom.

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
| **Zero.xyz** | token-gated extra tools; the executor's attachment lookup already routes through the tool registry | `integrations/zero/README.md`, `app/tools.py` |

## Team workflow (hackathon)

Push straight to `main`, `git pull --rebase` before you start. Ownership:
`app/` (engine) · `static/` + `data/` (UI & demo data) · `integrations/` +
`README.md` + slides (story). The API contract is the five endpoints in
`app/main.py` — change those only after telling the team.
