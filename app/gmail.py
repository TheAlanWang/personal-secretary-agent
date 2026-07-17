"""Real Gmail connection: IMAP + App Password, stdlib only (no new deps).

Setup on the Gmail side: enable 2-Step Verification, then create an App
Password at myaccount.google.com/apppasswords and paste it into the UI.

Local-first: credentials live in data/gmail.json on this machine only
(gitignored, chmod 600). Fetched mail is normalized into the exact same schema
as the mock inbox and the Nexla webhook, so the agents don't change at all.
"""
import email
import email.header
import email.utils
import imaplib
import json
import os
import re

from .store import DATA_DIR

CONFIG_PATH = os.path.join(DATA_DIR, "gmail.json")
IMAP_HOST = "imap.gmail.com"


def load_config():
    if not os.path.exists(CONFIG_PATH):
        return None
    with open(CONFIG_PATH) as f:
        return json.load(f)


def save_config(address, app_password):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump({"address": address, "app_password": app_password}, f)
    os.chmod(CONFIG_PATH, 0o600)


def delete_config():
    if os.path.exists(CONFIG_PATH):
        os.remove(CONFIG_PATH)


def test_connection(cfg):
    try:
        conn = _connect(cfg)
        conn.logout()
        return True, "connected as %s" % cfg["address"]
    except Exception as exc:
        return False, "connection failed: %s" % exc


def fetch_recent(cfg, limit=50):
    """Return the newest inbox messages in the normalized CPOS schema."""
    conn = _connect(cfg)
    try:
        _select_all_mail(conn)
        _, data = conn.uid("search", None, "ALL")
        uids = data[0].split()[-limit:]
        emails = []
        for uid in uids:
            status, msg_data = conn.uid("fetch", uid, "(X-GM-THRID RFC822)")
            if status != "OK" or not msg_data or not isinstance(msg_data[0], tuple):
                continue
            meta = msg_data[0][0].decode(errors="replace")
            thrid = re.search(r"X-GM-THRID (\d+)", meta)
            msg = email.message_from_bytes(msg_data[0][1])
            emails.append({
                "message_id": msg.get("Message-ID", "<uid-%s@gmail>" % uid.decode()),
                "thread_id": "gmail-" + (thrid.group(1) if thrid else uid.decode()),
                "from": email.utils.parseaddr(msg.get("From", ""))[1],
                "to": email.utils.parseaddr(msg.get("To", ""))[1],
                "date": msg.get("Date", ""),
                "subject": _decode_header(msg.get("Subject", "")),
                "body": _text_body(msg),
            })
        return emails
    finally:
        try:
            conn.logout()
        except Exception:
            pass


def _select_all_mail(conn):
    """Read '[Gmail]/All Mail' (inbox + archived, excludes Spam/Trash).
    Folder name is localized per account, so fall back to the IMAP
    special-use \\All flag, then to INBOX."""
    if conn.select('"[Gmail]/All Mail"', readonly=True)[0] == "OK":
        return
    status, data = conn.list()
    if status == "OK":
        for line in data:
            text = line.decode(errors="replace")
            if "\\All" in text:
                name = text.rsplit(' "/" ', 1)[-1].strip()
                if conn.select(name, readonly=True)[0] == "OK":
                    return
    conn.select("INBOX", readonly=True)


def _connect(cfg):
    conn = imaplib.IMAP4_SSL(IMAP_HOST, 993, timeout=15)
    # App passwords are shown by Google with spaces; accept either form.
    conn.login(cfg["address"], cfg["app_password"].replace(" ", ""))
    return conn


def _decode_header(value):
    return "".join(
        part.decode(charset or "utf-8", errors="replace") if isinstance(part, bytes) else part
        for part, charset in email.header.decode_header(value))


def _text_body(msg):
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode(part.get_content_charset() or "utf-8",
                                          errors="replace")
        return ""
    payload = msg.get_payload(decode=True)
    if payload is None:
        return ""
    return payload.decode(msg.get_content_charset() or "utf-8", errors="replace")
