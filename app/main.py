"""Buggy ingest API and dashboard server."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import init_db, record_event
from app.models import EventIn, EventOut


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Prepare the database before serving requests."""
    init_db()
    yield


app = FastAPI(title="Buggy", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    """Liveness probe used by Docker and uptime checks."""
    return {"ok": True}


@app.post("/api/events", response_model=EventOut, status_code=202)
def ingest_event(event: EventIn) -> EventOut:
    """Accept one error event and group it by fingerprint."""
    fingerprint, count = record_event(
        service=event.service,
        message=event.message,
        stack=event.stack,
        route=event.route,
        request_id=event.request_id,
        user_id=event.user_id,
        timestamp=event.timestamp,
    )
    return EventOut(fingerprint=fingerprint, count=count)
