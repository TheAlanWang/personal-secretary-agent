"""External tool registry — the Zero.xyz integration point.

The Planner/Executor sometimes need a capability outside the core set:
finding the right attachment, converting a document, resolving a link.
Those calls go through this registry instead of being hardcoded, so an
external provider (Zero.xyz) can supply tools without touching the agents.

Provider model:
  - "local"  — built-in fallbacks, always available, keeps the demo offline.
  - "zero"   — enabled when ZERO_API_KEY is set; each call is token-metered,
               which keeps agent tool usage accountable. Wire the actual
               endpoint in `_zero_call` once the sponsor API docs are in hand
               (see integrations/zero/README.md).
"""
import glob
import os

from . import store


def call(tool, query):
    """Route a tool call: Zero.xyz when configured, local fallback otherwise."""
    if os.environ.get("ZERO_API_KEY"):
        result = _zero_call(tool, query)
        if result is not None:
            return result
    return _LOCAL_TOOLS[tool](query)


def _zero_call(tool, query):
    # TODO(zero.xyz): call the sponsor API here with ZERO_API_KEY; return None
    # to fall back to the local tool on any failure.
    return None


def _find_attachment(query):
    """Local tool: find the file in data/ that best matches the query."""
    words = [w for w in query.lower().split() if len(w) > 2]
    for path in sorted(glob.glob(os.path.join(store.DATA_DIR, "*.*"))):
        name = os.path.basename(path).lower()
        if any(w in name for w in words):
            return "data/" + os.path.basename(path)
    return store.REPORT_PATH


_LOCAL_TOOLS = {
    "find_attachment": _find_attachment,
}
