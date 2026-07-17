"""Agent ② Planner — decides the smallest useful next action for a commitment:
block time, draft the reply, resend after a failed verification, or wait.

DRAFT_THRESHOLD_DAYS is the product's personality knob: how close to the
deadline before we stop preparing and start delivering.
"""
from datetime import date

from .. import models

DRAFT_THRESHOLD_DAYS = 2


def choose_next_action(record, today_iso):
    """Return an action dict, or None to wait."""
    # A failed verification always wins: repair the outcome first.
    if record["status"] == models.STATUS_RETRY:
        return {
            "type": models.ACTION_DRAFT_REPLY,
            "label": "Resend the reply in the same thread with the attachment included",
            "force_attachment": True,
        }

    days_left = (date.fromisoformat(record["deadline"]) - date.fromisoformat(today_iso)).days

    if not record["time_blocked"] and days_left > DRAFT_THRESHOLD_DAYS:
        return {
            "type": models.ACTION_BLOCK_TIME,
            "label": "Block 2 focus sessions before the %s deadline" % record["deadline"],
            "slots": ["%s 09:00-11:00" % today_iso, "focus session before %s" % record["deadline"]],
        }

    if days_left <= DRAFT_THRESHOLD_DAYS:
        return {
            "type": models.ACTION_DRAFT_REPLY,
            "label": "Draft a reply in this thread delivering: %s" % record["expected_outcome"],
            "force_attachment": False,
        }

    return None  # time already blocked, deadline not close: the right move is to wait
