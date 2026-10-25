"""Buggy ingest API and dashboard server."""

from fastapi import FastAPI

app = FastAPI(title="Buggy", version="0.1.0")


@app.get("/health")
def health() -> dict:
    """Liveness probe used by Docker and uptime checks."""
    return {"ok": True}
