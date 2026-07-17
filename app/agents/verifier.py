"""Agent ④ Outcome Verifier — checks what ACTUALLY happened against the
expected outcome. This is the "Loop" in CPOS Loop: an incomplete or wrong
outcome reopens the plan instead of silently counting as done.
"""
from .. import models


def verify(state, record):
    replies = [m for m in state["outbox"]
               if m["in_reply_to"] == record["thread_message_id"]]

    if not replies:
        _fail(record, "No reply found in the thread")
        return
    last = replies[-1]
    if last["thread_id"] != record["source_thread"]:
        _fail(record, "Reply landed in the WRONG thread")
        return
    if not last["attachments"]:
        _fail(record, "Reply is in the right thread but the report attachment is MISSING")
        return

    record["status"] = models.STATUS_CLOSED
    record["verifier_note"] = None
    models.log(record, "verifier",
               "Outcome verified: correct thread ✓, attachment present ✓ — loop closed")


def _fail(record, note):
    record["status"] = models.STATUS_RETRY
    record["verifier_note"] = note
    models.log(record, "verifier", "Verification FAILED: %s — reopening the loop" % note)
