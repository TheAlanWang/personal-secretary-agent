"""End-to-end smoke test: drives the full demo script without the web layer.

    python3 smoke.py

Expected: the commitment goes open -> block time -> draft reply -> verification
FAILS (injected missing attachment) -> retry -> resend -> closed.
"""
import json
import os

os.environ["LLM_DISABLED"] = "1"  # the test exercises the offline rule path

from app import engine, store


def step(state, label):
    rec = state["records"][0]
    print("%-42s status=%-18s" % (label, rec["status"]))
    return rec


def main():
    # in-memory copy: the test never touches data/state.json (the live demo's state)
    state = json.loads(json.dumps(store.DEFAULT_STATE))
    state["today"] = "2026-07-10"                     # pinned so the test is deterministic

    assert engine.sync(state) == 1, "extractor should find exactly 1 commitment"
    rec = step(state, "1. sync inbox")
    assert rec["deadline"] == "2026-07-18", rec["deadline"]

    engine.tick(state)
    rec = step(state, "2. tick -> planner proposes")
    assert rec["pending_action"]["type"] == "block_time"

    engine.approve(state, rec["id"])
    rec = step(state, "3. approve -> calendar blocked")
    assert rec["time_blocked"] and len(state["calendar"]) == 2

    state["today"] = "2026-07-17"                     # near deadline: planner switches gear
    engine.tick(state)
    rec = step(state, "4. near deadline, tick -> draft reply")
    assert rec["pending_action"]["type"] == "draft_reply"

    engine.approve(state, rec["id"])
    rec = step(state, "5. approve -> email 'sent'")
    assert rec["status"] == "verifying"
    assert state["outbox"][-1]["attachments"] == [], "demo trap should drop attachment"

    engine.tick(state)
    rec = step(state, "6. tick -> verifier catches it")
    assert rec["status"] == "retry", "THE LOOP: missing attachment must reopen the plan"

    engine.tick(state)
    rec = step(state, "7. tick -> repair auto-executed (no re-approval)")
    assert rec["status"] == "verifying"
    assert state["outbox"][-1]["attachments"], "resend must carry the attachment"

    engine.tick(state)
    rec = step(state, "8. tick -> verified, loop closed")
    assert rec["status"] == "closed"

    print("\nSMOKE PASS — full CPOS loop including one retry. Audit trail:")
    for h in rec["history"]:
        print("  [%-9s] %s" % (h["agent"], h["message"]))


if __name__ == "__main__":
    main()
