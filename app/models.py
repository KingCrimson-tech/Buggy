"""Pydantic request and response models for the Buggy API."""

from pydantic import BaseModel, Field


class EventIn(BaseModel):
    """Payload sent by the SDK when an error is captured."""

    service: str = Field(min_length=1)
    message: str = Field(min_length=1)
    stack: str = ""
    route: str = ""
    request_id: str = ""
    user_id: str = ""
    environment: str = "dev"
    timestamp: str | None = None


class EventOut(BaseModel):
    """Ingest acknowledgement."""

    fingerprint: str
    count: int


class ErrorItem(BaseModel):
    """One grouped error."""

    fingerprint: str
    service: str
    message: str
    count: int
    first_seen: str
    last_seen: str


class EventItem(BaseModel):
    """One raw occurrence of an error."""

    id: int
    route: str
    stack: str
    request_id: str
    user_id: str
    timestamp: str


class ErrorDetail(BaseModel):
    """A group plus its latest events."""

    error: ErrorItem
    events: list[EventItem]


class StatsOut(BaseModel):
    """Dashboard summary counters."""

    total_groups: int
    total_events: int
    events_today: int
