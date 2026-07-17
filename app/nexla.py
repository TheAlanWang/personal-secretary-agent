"""Nexla data pipeline layer.

Flow:  Gmail (IMAP fetch) → push raw normalized records to a Nexla api_push
       source → Nexla schema-detects into a Nexset → REST sink delivers to
       LUCY's /api/ingest webhook (token-guarded).

Provisioned via the Nexla API (org gmail.com-44584a9b):
  - data source 125809 "LUCY raw email push" (type api_push, ACTIVE)
  - source api key: data/nexla_push.json

Config resolution:
  1) env: NEXLA_PUSH_URL, NEXLA_SOURCE_API_KEY  (see .env.example)
  2) file: data/nexla_push.json {"push_url", "api_key"}
The push URL is the "webhook URL" shown in Nexla's source drawer (Config →
view tab). If unset or the push fails, callers fall back to local ingestion —
the loop never depends on the pipeline being up.

Set NEXLA_PRIMARY=1 to make Nexla the only ingest path (skip local ingestion
and let the sink deliver); default is mirror mode (push AND ingest locally —
message-id dedupe makes double delivery harmless).
"""
import json
import os
import ssl
import urllib.request

from .store import DATA_DIR

CONFIG_PATH = os.path.join(DATA_DIR, "nexla_push.json")


def _config():
    if os.environ.get("NEXLA_PUSH_URL"):
        return {"push_url": os.environ["NEXLA_PUSH_URL"],
                "api_key": os.environ.get("NEXLA_SOURCE_API_KEY", "")}
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            cfg = json.load(f)
            if cfg.get("push_url"):
                return cfg
    return None


def configured():
    return _config() is not None


def primary():
    """True when Nexla is the sole ingest path (no local fallback ingestion)."""
    return configured() and os.environ.get("NEXLA_PRIMARY") == "1"


def _ssl_context():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        if os.path.exists("/etc/ssl/cert.pem"):
            return ssl.create_default_context(cafile="/etc/ssl/cert.pem")
        return ssl.create_default_context()


def push_records(emails):
    """Push a batch of normalized email records into the Nexla source.
    Returns True on success; False (never raises) so callers can fall back."""
    cfg = _config()
    if not cfg or not emails:
        return False
    headers = {"Content-Type": "application/json"}
    if cfg.get("api_key"):
        headers["X-Api-Key"] = cfg["api_key"]
    req = urllib.request.Request(cfg["push_url"], data=json.dumps(emails).encode(),
                                 headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30, context=_ssl_context()) as resp:
            return 200 <= resp.status < 300
    except Exception:
        return False
