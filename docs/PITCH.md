# LUCY — 3-Minute Pitch Script

## 0:00–0:30 · The problem

> Raise your hand if an email assistant has ever *written* something for you.
> Now keep it up if one has ever *checked that the thing you promised actually
> got done*. That's the gap.
>
> Productivity doesn't die from too much email. It dies from **broken
> commitments**: a promise made in a thread three weeks ago, a deadline nobody
> is tracking, an outcome nobody verifies.

## 0:30–1:00 · The idea

> LUCY is a **local-first personal secretary** that tracks four things for
> every commitment hiding in your inbox: the **C**ommitment, the **P**erson who
> owns it, the expected **O**utcome, and the **S**chedule — the CPOS loop.
>
> Four agents run that loop: an **Extractor** finds the promise, a **Planner**
> picks the smallest useful action, an **Executor** acts — new intents need
> *your* approval — and a **Verifier** checks what *actually happened*. Wrong
> outcome? The loop repairs it itself, under the approval you already gave.

## 1:00–2:20 · Live demo (drive the UI, narrate the beats)

1. **Live email** — teammate sends the professor's ask to the connected Gmail
   on stage — "That's a real email arriving right now. Within seconds the
   extractor turns it into a tracked commitment — deadline July 23, owner,
   expected outcome: report in this same thread."
   *(Wi-Fi dies? `curl -X POST localhost:8010/api/sync` loads the identical
   demo email — rehearse both.)*
2. **Approve** — "Deadline's six days out, so the planner doesn't write
   anything yet. Smallest useful action: block two writing sessions. I approve;
   they're on my calendar. Notice I never drive the loop — it ticks itself."
3. **Fast-forward to July 22 → Approve** — "Now it drafts the submission
   reply — same thread, report attached. I approve. Sent."
4. **THE MOMENT — hands off the keyboard** *(card pulses red)* — "But look:
   the verifier checked the sent mail and the attachment is **missing**. Any
   other assistant would have called this done. Watch — LUCY reopens the loop,
   resends *with* the attachment under the approval I already gave, verifies —
   loop closed. I didn't touch anything."
5. Point at the audit trail — "Every line: which agent, what action, approved
   by whom."

## 2:20–2:50 · How it's built (sponsors)

> - **Nexla** owns the data plane: it normalizes raw email into one schema and
>   delivers to our live webhook — the demo inbox and Nexla speak the exact
>   same format, so going live is config, not code.
> - **Pomerium** owns permissions: per-agent least privilege — the extractor
>   *cannot* send email, sending requires a human-approved request, and every
>   action is in the access log.
> - **Akash** owns compute: stateless vLLM workers on decentralized GPU —
>   minimal prompts out, structured JSON back, nothing retained. Your data
>   never leaves your machine; one env var switches the agents from rules to
>   LLM, and they fall back gracefully.

## 2:50–3:00 · Close

> Assistants that write are everywhere. **LUCY is the one that makes sure it
> got done.** Thank you.

---

## Judge Q&A cheat sheet

- **"What if the LLM hallucinates a commitment?"** — No *new* intent executes
  without human approval; a bad extraction dies at the Approve button, and the
  record shows exactly which agent proposed it.
- **"If humans approve everything, where's the loop?"** — Approval is per
  *intent*, not per attempt: you approve "submit the report in that thread"
  once, and the machine owns the retries until reality matches it. Humans gate
  intents; the loop owns attempts.
- **"Why local-first?"** — Email is the most sensitive dataset most people
  own. State lives in one JSON file on your machine; only minimal, stateless
  prompts go to the Akash worker.
- **"Is the sponsor integration real?"** — The webhook endpoint is live
  (`/api/ingest`, token-guarded), the Pomerium policy and Akash SDL are real
  syntax in `integrations/`, and `LLM_BASE_URL` hot-swaps the inference
  backend today. What remains is wiring credentials, not writing code.
- **"How does the verifier actually check?"** — Deterministically, not by
  vibes: it re-reads the sent thread and asserts thread ID matches and the
  attachment list is non-empty. Code decides state transitions; the LLM only
  proposes.
- **"What's next?"** — Calendar/docs sources through the same Nexla schema,
  counterparty-owned commitments (waiting-on-them nudges), and an approvals
  inbox on mobile.
