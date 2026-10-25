"""Demo API that reports its errors to Buggy."""

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sdk.buggy import capture_exception, init  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Point the SDK at the local Buggy instance."""
    init(
        dsn="http://localhost:8000/api/events",
        service="demo-api",
        environment="dev",
    )
    yield


app = FastAPI(title="Buggy Demo API", version="0.1.0", lifespan=lifespan)


@app.get("/ok")
def ok() -> dict:
    """A route that never fails."""
    return {"ok": True}


@app.get("/fail")
def fail(msg: str = "Something exploded") -> dict:
    """Unhandled error, grouped by the message."""
    raise RuntimeError(msg)


@app.get("/user-fail/{user_id}")
def user_fail(user_id: int) -> dict:
    """Fails per user, but all users share one fingerprint."""
    raise ValueError(f"Payment failed for order {user_id}")


@app.exception_handler(Exception)
async def report_exception(request: Request, exc: Exception) -> JSONResponse:
    """Forward unhandled errors to Buggy, then return a JSON 500."""
    capture_exception(exc, route=f"{request.method} {request.url.path}")
    return JSONResponse(
        status_code=500,
        content={"ok": False, "error": "internal server error"},
    )
