"""Pluggable LLM client.

V1 runs fully offline with rule-based agents. To switch to a private stateless
worker on Akash, deploy vLLM (see integrations/akash/deploy.yaml) and set:

    export LLM_BASE_URL=https://<akash-endpoint>/v1
    export LLM_MODEL=Qwen/Qwen2.5-7B-Instruct

Agents call `complete_json()`; if no endpoint is configured it returns None and
the caller falls back to its rule-based logic.
"""
import json
import os
import urllib.request


def complete_json(system_prompt, user_prompt):
    base_url = os.environ.get("LLM_BASE_URL")
    if not base_url:
        return None
    payload = {
        "model": os.environ.get("LLM_MODEL", "default"),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0,
    }
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + os.environ.get("LLM_API_KEY", "none"),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = json.load(resp)["choices"][0]["message"]["content"]
        return json.loads(content)
    except Exception:
        return None  # stateless worker unreachable -> rule-based fallback
