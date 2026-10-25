"""Tiny error-reporting SDK. Only depends on requests and the stdlib."""

import functools
import sys
import traceback
from datetime import datetime, timezone

import requests

_config = {"dsn": None, "service": None, "environment": "dev"}
_original_excepthook = sys.excepthook


def init(dsn: str, service: str, environment: str = "dev") -> None:
    """Configure the SDK. Call once at process start."""
    _config["dsn"] = dsn.rstrip("/")
    _config["service"] = service
    _config["environment"] = environment


def _payload(
    exc: BaseException,
    route: str = "",
    user_id: str = "",
    request_id: str = "",
) -> dict:
    """Build the JSON body accepted by POST /api/events."""
    message = str(exc) or type(exc).__name__
    stack = "".join(
        traceback.format_exception(type(exc), exc, exc.__traceback__)
    )
    return {
        "service": _config["service"],
        "message": message,
        "stack": stack,
        "route": route,
        "request_id": request_id,
        "user_id": user_id,
        "environment": _config["environment"],
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def capture_exception(
    exc: BaseException,
    route: str = "",
    user_id: str = "",
    request_id: str = "",
) -> str | None:
    """Report an exception and return its fingerprint, or None on any failure."""
    try:
        if not _config["dsn"] or not _config["service"]:
            return None
        response = requests.post(
            _config["dsn"],
            json=_payload(exc, route, user_id, request_id),
            timeout=2,
        )
        response.raise_for_status()
        return response.json().get("fingerprint")
    except Exception:
        return None


def handle_exception(route: str = ""):
    """Decorator that reports any exception raised by the wrapped function."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                capture_exception(exc, route=route)
                raise
        return wrapper
    return decorator


def install_excepthook() -> None:
    """Report uncaught exceptions that crash the process."""
    def hook(exc_type, exc, tb):
        capture_exception(exc)
        _original_excepthook(exc_type, exc, tb)

    sys.excepthook = hook
