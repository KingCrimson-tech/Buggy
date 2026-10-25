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
