"""CPOS Loop — FastAPI entry point.

Run:  uvicorn app.main:app --reload
Open: http://localhost:8000
"""
import os

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import engine, store

app = FastAPI(title="CPOS Loop")

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")


class TodayBody(BaseModel):
    date: str


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
def ingest(email: dict):
    """Webhook destination for the Nexla flow (integrations/nexla/README.md):
    receives one normalized email and runs the extractor on it."""
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


@app.post("/api/today")
def set_today(body: TodayBody):
    state = store.load_state()
    state["today"] = body.date
    store.save_state(state)
    return {"today": state["today"]}


@app.post("/api/reset")
def reset():
    store.reset_state()
    return {"ok": True}
