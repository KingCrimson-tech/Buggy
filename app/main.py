"""Buggy ingest API and dashboard server."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query

from app.db import (
    get_error,
    get_events,
    get_stats,
    init_db,
    list_errors,
    record_event,
)
from app.models import (
    ErrorDetail,
    ErrorItem,
    EventIn,
    EventOut,
    StatsOut,
)


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


@app.get("/api/errors", response_model=list[ErrorItem])
def list_error_groups(
    search: str = "",
    service: str = "",
    limit: int = Query(50, ge=1, le=500),
) -> list[dict]:
    """List error groups, optionally filtered by message text or service."""
    return list_errors(search=search, service=service, limit=limit)


@app.get("/api/errors/{fingerprint}", response_model=ErrorDetail)
def error_detail(
    fingerprint: str,
    events_limit: int = Query(20, ge=1, le=500),
) -> dict:
    """Return one error group with its latest raw events."""
    error = get_error(fingerprint)
    if error is None:
        raise HTTPException(status_code=404, detail="Error group not found")
    return {"error": error, "events": get_events(fingerprint, limit=events_limit)}


@app.get("/api/stats", response_model=StatsOut)
def stats() -> dict:
    """Return summary counters for the dashboard header."""
    return get_stats()
