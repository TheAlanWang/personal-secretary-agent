"""Agent ③ Executor — carries out an approved action. It only ever runs after
the user clicks Approve (the Pomerium gate in production, see
integrations/pomerium/policy.yaml).

Sending is mocked: "sent" email goes to state["outbox"], calendar holds go to
state["calendar"]. `inject_failure` is the demo trap: the first send silently
drops the attachment so the Verifier has something real to catch.
"""
from .. import models, tools


def execute(state, record):
    action = record["pending_action"]
    record["pending_action"] = None

    if action["type"] == models.ACTION_BLOCK_TIME:
        for slot in action["slots"]:
            state["calendar"].append({"commitment": record["id"], "slot": slot,
                                      "title": "Work on: %s" % record["promise"][:48]})
        record["time_blocked"] = True
        record["status"] = models.STATUS_IN_PROGRESS
        models.log(record, "executor", "Calendar holds created: %s" % ", ".join(action["slots"]))
        return

    if action["type"] == models.ACTION_DRAFT_REPLY:
        # Attachment lookup goes through the tool registry (Zero.xyz seam).
        attachments = [tools.call("find_attachment", record["promise"])]
        if state["inject_failure"] and not action.get("force_attachment"):
            attachments = []          # oops — the very bug CPOS exists to catch
            state["inject_failure"] = False
        state["outbox"].append({
            "thread_id": record["source_thread"],
            "in_reply_to": record["thread_message_id"],
            "to": record["counterparty"],
            "subject": "Re: " + record["subject"],
            "body": "Hi,\n\nFollowing up in this thread as promised: %s\n\n"
                    "Please find the relevant file attached.\n\nBest regards"
                    % record["promise"][:200],
            "attachments": attachments,
        })
        record["status"] = models.STATUS_VERIFYING
        models.log(record, "executor",
                   "Reply sent in thread '%s' (%d attachment(s))"
                   % (record["subject"], len(attachments)))
