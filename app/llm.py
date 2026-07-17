"""Pluggable LLM client — Akash (AkashML) or any OpenAI-compatible endpoint.

Config resolution order:
  1) env vars: LLM_BASE_URL, LLM_MODEL, LLM_API_KEY
  2) local file data/llm.json: {"base_url", "model", "api_key"}  (gitignored)
Set LLM_DISABLED=1 to force rule-based agents (smoke.py does this).

Agents call complete_json(); any failure returns None and the caller falls
back to its rule-based logic, so the demo never dies with the network.
"""
import json
import os
import ssl
import urllib.error
import urllib.request

from .store import DATA_DIR

LLM_CONFIG_PATH = os.path.join(DATA_DIR, "llm.json")


def config():
    if os.environ.get("LLM_DISABLED"):
        return None
    if os.environ.get("LLM_BASE_URL"):
        return {"base_url": os.environ["LLM_BASE_URL"],
                "model": os.environ.get("LLM_MODEL", "default"),
                "api_key": os.environ.get("LLM_API_KEY", "none")}
    if os.path.exists(LLM_CONFIG_PATH):
        with open(LLM_CONFIG_PATH) as f:
            return json.load(f)
    return None


def _ssl_contexts():
    """Verification stays ON in every context; we only vary the CA bundle
    (python.org builds often ship without one wired up on macOS)."""
    yield ssl.create_default_context()
    try:
        import certifi
        yield ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        pass
    if os.path.exists("/etc/ssl/cert.pem"):  # macOS system CA bundle
        yield ssl.create_default_context(cafile="/etc/ssl/cert.pem")


def complete_json(system_prompt, user_prompt):
    cfg = config()
    if not cfg:
        return None
    body = json.dumps({
        "model": cfg.get("model", "default"),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0,
        "max_tokens": 400,
    }).encode()
    url = cfg["base_url"].rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json",
               "Authorization": "Bearer " + cfg.get("api_key", "none")}
    for ctx in _ssl_contexts():
        req = urllib.request.Request(url, data=body, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
                content = json.load(resp)["choices"][0]["message"]["content"]
            return _parse_json(content)
        except urllib.error.URLError as exc:
            if "CERTIFICATE" in str(exc).upper():
                continue  # try the next, more permissive SSL context
            return None
        except Exception:
            return None
    return None


def _parse_json(content):
    """Models love ```json fences and prose around the JSON — dig it out."""
    text = content.strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(text[start:end + 1])
    except ValueError:
        return None
