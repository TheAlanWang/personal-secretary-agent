"""Local-first state store: everything lives in data/state.json on the user's machine."""
import json
import os
from datetime import date

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
STATE_PATH = os.path.join(DATA_DIR, "state.json")
SAMPLE_EMAILS_PATH = os.path.join(DATA_DIR, "sample_emails.json")
REPORT_PATH = "data/phase1_report.pdf"

DEFAULT_STATE = {
    "today": None,               # always overwritten with the real date on load
    "inject_failure": True,      # demo trap: first send silently drops the attachment
    "next_id": 1,
    "records": [],
    "scanned": {},               # message_id -> verdict; every email LUCY read, visible + never re-scanned
    "judgments": {},             # message_id -> raw LLM judgment; survives reset so rebuilds cost zero LLM calls
    "outbox": [],                # stands in for "sent email" (mock SMTP)
    "calendar": [],              # stands in for the user's calendar
}


def load_state():
    if not os.path.exists(STATE_PATH):
        state = json.loads(json.dumps(DEFAULT_STATE))
    else:
        with open(STATE_PATH) as f:
            state = json.load(f)
    state["today"] = date.today().isoformat()  # production behavior: the real clock
    return state


def save_state(state):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def reset_state():
    old = load_state() if os.path.exists(STATE_PATH) else None
    state = json.loads(json.dumps(DEFAULT_STATE))
    state["today"] = date.today().isoformat()
    if old:
        # Reset restarts the demo loop, not LUCY's judgment: junk verdicts and
        # all cached LLM judgments survive, so the rebuild costs zero LLM calls.
        state["scanned"] = {mid: e for mid, e in old.get("scanned", {}).items()
                            if e["verdict"].startswith("no commitment")}
        state["judgments"] = old.get("judgments", {})
    save_state(state)
    return state


def load_sample_emails():
    with open(SAMPLE_EMAILS_PATH) as f:
        return json.load(f)
