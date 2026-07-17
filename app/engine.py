"""The CPOS loop driver: sync -> tick -> approve -> tick -> ... until closed.

Pure Python (no web framework) so both main.py (FastAPI) and smoke.py (the
end-to-end demo test) drive the exact same code.
"""
from . import models, store
from .agents import executor, extractor, planner, verifier

PLANNABLE = (models.STATUS_OPEN, models.STATUS_IN_PROGRESS, models.STATUS_RETRY)


def sync(state):
    """Ingest normalized emails (mock inbox / Nexla webhook) into CommitmentRecords."""
    known_threads = {r["source_thread"] for r in state["records"]}
    created = 0
    for email in store.load_sample_emails():
        created += ingest_email(state, email, known_threads)
    return created


def ingest_email(state, email, known_threads=None):
    if known_threads is None:
        known_threads = {r["source_thread"] for r in state["records"]}
    if email["thread_id"] in known_threads:
        return 0
    record = extractor.extract(state, email)
    if record is None:
        return 0
    state["records"].append(record)
    known_threads.add(email["thread_id"])
    return 1


def tick(state):
    """Advance every commitment one step through the loop."""
    for record in state["records"]:
        if record["status"] in PLANNABLE:
            action = planner.choose_next_action(record, state["today"])
            if action is None:
                models.log(record, "planner",
                           "Nothing useful to do yet (time blocked, deadline not close) — waiting")
                continue
            record["pending_action"] = action
            record["status"] = models.STATUS_AWAITING_APPROVAL
            models.log(record, "planner", "Proposed action: %s" % action["label"])
        elif record["status"] == models.STATUS_VERIFYING:
            verifier.verify(state, record)


def approve(state, rec_id):
    record = _find(state, rec_id)
    if record and record["status"] == models.STATUS_AWAITING_APPROVAL:
        models.log(record, "user", "APPROVED: %s" % record["pending_action"]["label"])
        executor.execute(state, record)


def reject(state, rec_id):
    record = _find(state, rec_id)
    if record and record["status"] == models.STATUS_AWAITING_APPROVAL:
        models.log(record, "user", "REJECTED: %s" % record["pending_action"]["label"])
        record["pending_action"] = None
        record["status"] = models.STATUS_REJECTED


def _find(state, rec_id):
    return next((r for r in state["records"] if r["id"] == rec_id), None)
