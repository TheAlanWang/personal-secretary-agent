"""CPOS Loop — FastAPI entry point.

Run:  uvicorn app.main:app --reload
Open: http://localhost:8000
"""
import os

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import engine, gmail, store

app = FastAPI(title="CPOS Loop")

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")


class GmailBody(BaseModel):
    address: str
    app_password: str


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/api/state")
def get_state():
    return store.load_state()


@app.post("/api/sync")
def sync():
    state = store.load_state()
    created = engine.sync(state)
    store.save_state(state)
    return {"created": created}


@app.post("/api/ingest")
def ingest(email: dict, request: Request, x_ingest_token: str = Header(default="")):
    """Webhook destination for the Nexla flow (integrations/nexla/README.md):
    receives one normalized email and runs the extractor on it.

    Fail-closed: without INGEST_TOKEN configured, only loopback clients are
    accepted; any exposure beyond localhost requires the shared secret (and in
    production Pomerium fronts this route).
    """
    expected = os.environ.get("INGEST_TOKEN")
    if expected:
        if x_ingest_token != expected:
            raise HTTPException(status_code=401, detail="invalid ingest token")
    else:
        client = request.client.host if request.client else ""
        if client not in ("127.0.0.1", "::1", "testclient"):
            raise HTTPException(status_code=503,
                                detail="set INGEST_TOKEN before exposing /api/ingest")
    required = {"message_id", "thread_id", "from", "to", "subject", "body"}
    missing = required - email.keys()
    if missing:
        raise HTTPException(status_code=422, detail="missing fields: %s" % sorted(missing))
    state = store.load_state()
    created = engine.ingest_email(state, email)
    store.save_state(state)
    return {"created": created}


@app.post("/api/tick")
def tick():
    state = store.load_state()
    engine.tick(state)
    store.save_state(state)
    return {"ok": True}


@app.post("/api/approve/{rec_id}")
def approve(rec_id: str):
    state = store.load_state()
    engine.approve(state, rec_id)
    store.save_state(state)
    return {"ok": True}


@app.post("/api/reject/{rec_id}")
def reject(rec_id: str):
    state = store.load_state()
    engine.reject(state, rec_id)
    store.save_state(state)
    return {"ok": True}


@app.post("/api/reset")
def reset():
    store.reset_state()
    return {"ok": True}


@app.get("/api/gmail")
def gmail_status():
    cfg = gmail.load_config()
    return {"configured": bool(cfg), "address": cfg["address"] if cfg else None}


@app.post("/api/gmail")
def gmail_configure(body: GmailBody):
    """Validate the credentials against imap.gmail.com before saving locally."""
    ok, message = gmail.test_connection(
        {"address": body.address, "app_password": body.app_password})
    if ok:
        gmail.save_config(body.address, body.app_password)
    return {"ok": ok, "message": message}


@app.delete("/api/gmail")
def gmail_disconnect():
    gmail.delete_config()
    return {"ok": True}


@app.post("/api/gmail/sync")
def gmail_sync():
    cfg = gmail.load_config()
    if not cfg:
        raise HTTPException(status_code=400, detail="Gmail is not connected yet")
    state = store.load_state()
    try:
        emails = gmail.fetch_new(cfg, set(state.get("scanned", {}).keys()))
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Gmail fetch failed: %s" % exc)
    created = sum(engine.ingest_email(state, e) for e in emails)
    store.save_state(state)
    return {"fetched": len(emails), "created": created}
