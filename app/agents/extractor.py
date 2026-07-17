"""Agent ① Commitment Extractor — reads a normalized email (from Nexla) and
finds the commitment: promise, owner, deadline, expected outcome.

Tries the LLM worker first; falls back to rule-based extraction so the demo
runs with zero API keys.
"""
import re

from .. import llm, models

MONTHS = {m: i + 1 for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"])}

DATE_RE = re.compile(r"(January|February|March|April|May|June|July|August|"
                     r"September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})")

SYSTEM_PROMPT = (
    "Extract the commitment from this email as JSON with keys: "
    "promise, deadline (ISO date), expected_outcome. Return JSON only."
)


def extract(state, email):
    """Return a new CommitmentRecord for this email, or None if no commitment found."""
    result = llm.complete_json(SYSTEM_PROMPT, email["body"])
    if result is None:
        result = _rule_based(email["body"])
    if result is None:
        return None
    record = models.new_record(
        rec_id="cpos-%03d" % state["next_id"],
        email=email,
        promise=result["promise"],
        deadline=result["deadline"],
        expected_outcome=result["expected_outcome"],
    )
    state["next_id"] += 1
    models.log(record, "extractor",
               "Commitment found in thread '%s': %s (deadline %s)"
               % (email["subject"], result["promise"], result["deadline"]))
    return record


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
