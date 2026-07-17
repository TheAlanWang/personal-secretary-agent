"""Agent ① Commitment Extractor — reads a normalized email (mock, Nexla
webhook, or real Gmail) and decides whether it contains a real commitment.

LLM-first (Akash worker): understands any language and relative dates, and
filters out newsletters/receipts/notifications. If the LLM is unreachable it
falls back to rule-based extraction so the demo runs with zero keys.
"""
import re
from datetime import date, timedelta

from .. import llm, models

MONTHS = {m: i + 1 for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"])}

DATE_RE = re.compile(r"(January|February|March|April|May|June|July|August|"
                     r"September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})")

SYSTEM_PROMPT = (
    "You are the commitment extractor of a personal secretary. Given one email, "
    "decide whether it contains a REAL commitment or task with a deadline — in any "
    "language. Respond with ONLY this JSON, no prose:\n"
    '{"commitment": true|false, "promise": "...", "deadline": "YYYY-MM-DD", '
    '"expected_outcome": "..."}\n'
    "Rules: newsletters, receipts, verification codes, promotions, security alerts, "
    "social notifications, and pure FYI notifications are NOT commitments "
    "(commitment=false). But a genuine task or request addressed to the recipient "
    "COUNTS even without an explicit date — e.g. 'please review', 'let me know what "
    "you think', an invitation that needs an RSVP: set commitment=true and deadline "
    "to null. Resolve relative dates (\"next Thursday\", \"明天\", \"下周五\") to ISO "
    "dates using the reference dates provided. Write promise and expected_outcome in "
    "the email's own language."
)


def extract(state, email):
    """Return a new CommitmentRecord for this email, or None if no commitment."""
    prompt = ("Today: %s\nEmail date: %s\nFrom: %s\nSubject: %s\n\n%s" % (
        state.get("today"), email.get("date", "?"), email["from"],
        email["subject"], email["body"][:4000]))
    result = llm.complete_json(SYSTEM_PROMPT, prompt)

    assumed_deadline = False
    if result is None:                       # LLM unreachable -> offline rules
        result = _rule_based(email["body"])
        brain = "rules"
    else:
        brain = "akash-llm"
        if not (result.get("commitment") and result.get("promise")):
            return None                      # the AI filtered this email out
        if not _valid_date(result.get("deadline")):
            # Real task without an explicit date: track it with a soft deadline
            # rather than dropping it on the floor.
            result["deadline"] = (date.fromisoformat(state["today"])
                                  + timedelta(days=3)).isoformat()
            assumed_deadline = True
    if result is None:
        return None

    record = models.new_record(
        rec_id="cpos-%03d" % state["next_id"],
        email=email,
        promise=result["promise"],
        deadline=result["deadline"],
        expected_outcome=result.get("expected_outcome")
        or "Reply delivered in the same email thread",
    )
    state["next_id"] += 1
    models.log(record, "extractor",
               "Commitment found (%s) in '%s': %s (deadline %s%s)"
               % (brain, email["subject"], record["promise"], record["deadline"],
                  ", assumed — no explicit date in the email" if assumed_deadline else ""))
    return record


def _valid_date(value):
    try:
        date.fromisoformat(value or "")
        return True
    except ValueError:
        return False


def _rule_based(body):
    date_match = DATE_RE.search(body)
    if not date_match:
        return None
    month, day, year = date_match.groups()
    deadline = "%s-%02d-%02d" % (year, MONTHS[month], int(day))

    promise = None
    for sentence in re.split(r"(?<=[.!?])\s+", body):
        if re.search(r"\b(submit|send|deliver|finish|complete)\b", sentence, re.I):
            promise = sentence.strip()
            break
    if promise is None:
        return None

    outcome = "Reply delivered in the same email thread"
    if re.search(r"\b(report|attach|attachment|document)\b", body, re.I):
        outcome = "Report attached as a reply in the same email thread"
    return {"promise": promise, "deadline": deadline, "expected_outcome": outcome}
