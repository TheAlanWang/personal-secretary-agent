"""Core data model for CPOS Loop: the CommitmentRecord and its state machine.

State machine:
    open ──► awaiting_approval ──► in_progress ──► awaiting_approval ──► verifying ──► closed
                 (block time)                        (send email)           │
                                                        ▲                   ▼
                                                        └───── retry ◄──────┘
                                                       (re-plan, loop again)
"""

STATUS_OPEN = "open"                            # commitment extracted, not yet planned
STATUS_AWAITING_APPROVAL = "awaiting_approval"  # action prepared, user must approve
STATUS_IN_PROGRESS = "in_progress"              # early action done, waiting for the right time
STATUS_VERIFYING = "verifying"                  # action executed, verifier must check outcome
STATUS_RETRY = "retry"                          # verification failed -> planner re-plans
STATUS_CLOSED = "closed"                        # outcome verified, loop closed
STATUS_REJECTED = "rejected"                    # user rejected the pending action

ACTION_BLOCK_TIME = "block_time"
ACTION_DRAFT_REPLY = "draft_reply"
ACTION_WAIT = "wait"


def new_record(rec_id, email, promise, deadline, expected_outcome):
    return {
        "id": rec_id,
        "source_thread": email["thread_id"],
        "thread_message_id": email["message_id"],
        "subject": email["subject"],
        "counterparty": email["from"],
        "owner": "user",
        "promise": promise,
        "deadline": deadline,  # ISO date, e.g. "2026-07-23"
        "expected_outcome": expected_outcome,
        "status": STATUS_OPEN,
        "time_blocked": False,
        "pending_action": None,
        "verifier_note": None,
        "history": [],
    }


def log(record, agent, message):
    entry = {"agent": agent, "message": message}
    if record["history"] and record["history"][-1] == entry:
        return  # the auto-loop ticks repeatedly; don't spam identical lines
    record["history"].append(entry)
