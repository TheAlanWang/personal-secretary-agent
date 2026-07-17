"""The CPOS loop driver: sync -> tick -> approve -> tick -> ... until closed.

Pure Python (no web framework) so both main.py (FastAPI) and smoke.py (the
end-to-end demo test) drive the exact same code.
"""
from concurrent.futures import ThreadPoolExecutor

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
    scanned = state.setdefault("scanned", {})
    if email["message_id"] in scanned:
        return 0  # already judged once — never re-send the same mail to the LLM
    if known_threads is None:
        known_threads = {r["source_thread"] for r in state["records"]}
    if email["thread_id"] in known_threads:
        _record_scan(scanned, email, "thread already tracked")
        return 0
    return _apply_judgment(state, known_threads, email, _cached_judge(state, email))


def _cached_judge(state, email):
    cache = state.setdefault("judgments", {})
    mid = email["message_id"]
    if mid not in cache:
        cache[mid] = {"j": extractor.judge(state.get("today"), email)}
        while len(cache) > 500:
            cache.pop(next(iter(cache)))
    return cache[mid]["j"]


def ingest_batch(state, emails):
    """Judge many new emails in parallel (LLM calls are independent), then
    apply results serially (state mutation stays single-threaded)."""
    scanned = state.setdefault("scanned", {})
    known_threads = {r["source_thread"] for r in state["records"]}
    todo = []
    for email in emails:
        if email["message_id"] in scanned:
            continue
        if email["thread_id"] in known_threads:
            _record_scan(scanned, email, "thread already tracked")
            continue
        todo.append(email)
    if not todo:
        return 0
    cache = state.setdefault("judgments", {})
    fresh = [e for e in todo if e["message_id"] not in cache]
    if fresh:  # only uncached emails cost LLM calls, six at a time
        with ThreadPoolExecutor(max_workers=6) as pool:
            for email, judgment in zip(fresh, pool.map(
                    lambda e: extractor.judge(state.get("today"), e), fresh)):
                cache[email["message_id"]] = {"j": judgment}
        while len(cache) > 500:
            cache.pop(next(iter(cache)))
    return sum(_apply_judgment(state, known_threads, email, cache[email["message_id"]]["j"])
               for email in todo)


def _apply_judgment(state, known_threads, email, judgment):
    scanned = state["scanned"]
    if email["thread_id"] in known_threads:  # a batch-mate already created this thread's card
        _record_scan(scanned, email, "thread already tracked")
        return 0
    if judgment is None:
        _record_scan(scanned, email, "no commitment — filtered out")
        return 0
    record = extractor.build_record(state, email, judgment)
    state["records"].append(record)
    known_threads.add(email["thread_id"])
    _record_scan(scanned, email, "commitment → %s" % record["id"])
    return 1


def _record_scan(scanned, email, verdict):
    scanned[email["message_id"]] = {
        "subject": email["subject"], "from": email["from"],
        "date": email.get("date", ""), "verdict": verdict,
    }
    while len(scanned) > 200:  # keep the feed bounded
        scanned.pop(next(iter(scanned)))


def tick(state):
    """Advance every commitment one step through the loop."""
    for record in state["records"]:
        if record["status"] in PLANNABLE:
            was_retry = record["status"] == models.STATUS_RETRY
            action = planner.choose_next_action(record, state["today"])
            if action is None:
                models.log(record, "planner",
                           "Nothing useful to do yet (time blocked, deadline not close) — waiting")
                continue
            record["pending_action"] = action
            models.log(record, "planner", "Proposed action: %s" % action["label"])
            if was_retry:
                # Repairing an outcome the user already approved: the approval
                # covers the intent, so the loop closes itself hands-off.
                models.log(record, "executor",
                           "Auto-executing repair — inherits the user's original approval")
                executor.execute(state, record)
            else:
                record["status"] = models.STATUS_AWAITING_APPROVAL
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
