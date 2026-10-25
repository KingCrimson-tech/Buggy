"""SQLite setup, fingerprinting, and event persistence."""

import hashlib
import os
import re
import sqlite3
from datetime import datetime
from contextlib import closing
from webbrowser import get

DB_PATH = os.getenv("BUGGY_DB", "buggy.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS errors(
  fingerprint TEXT PRIMARY KEY,
  service TEXT NOT NULL, message TEXT NOT NULL,
  first_seen TEXT NOT NULL, last_seen TEXT NOT NULL,
  count INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS events(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  fingerprint TEXT NOT NULL,
  service TEXT NOT NULL, route TEXT DEFAULT '',
  stack TEXT DEFAULT '', request_id TEXT DEFAULT '',
  user_id TEXT DEFAULT '', timestamp TEXT NOT NULL,
  FOREIGN KEY (fingerprint) REFERENCES errors(fingerprint)
);
CREATE INDEX IF NOT EXISTS idx_events_fp ON events(fingerprint);
CREATE INDEX IF NOT EXISTS idx_errors_last ON errors(last_seen);
"""


def utc_now() -> str:
    """Return the current UTC time as an ISO8601 string ending in Z."""
    return datetime.utcnow().isoformat() + "Z"


def get_conn() -> sqlite3.Connection:
    """Open a connection to the Buggy database."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Create the schema if it does not exist yet."""
    with get_conn() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA)


def normalize_message(msg: str) -> str:
    """Strip variable data (numbers, quoted strings) from an error message."""
    msg = re.sub(r"\d+", "*", msg)
    msg = re.sub(r"'[^']*'", "'*'", msg)
    msg = re.sub(r'"[^"]*"', '"*"', msg)
    msg = " ".join(msg.split())
    return msg[:500]


def extract_frames(stack: str) -> str:
    """Keep the first three stack frames, masking line numbers."""
    frames = [line.strip() for line in stack.splitlines() if 'File "' in line]
    frames = [re.sub(r", line \d+", ", line *", frame) for frame in frames[:3]]
    return "|".join(frames)


def make_fingerprint(service: str, message: str, stack: str) -> str:
    """Compute the stable group key for an error."""
    normalized = normalize_message(message)
    frames = extract_frames(stack)
    raw = f"{service}|{normalized}|{frames}".encode()
    return hashlib.sha1(raw).hexdigest()[:16]


def record_event(
    service: str,
    message: str,
    stack: str = "",
    route: str = "",
    request_id: str = "",
    user_id: str = "",
    timestamp: str | None = None,
) -> tuple[str, int]:
    """Persist an event and return its fingerprint and total group count."""
    fingerprint = make_fingerprint(service, message, stack)
    now = utc_now()
    event_time = timestamp or now

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO errors(fingerprint, service, message, first_seen, last_seen, count)
            VALUES (?, ?, ?, ?, ?, 1)
            ON CONFLICT(fingerprint) DO UPDATE SET
              count = count + 1,
              last_seen = excluded.last_seen
            """,
            (fingerprint, service, message, now, now),
        )
        conn.execute(
            """
            INSERT INTO events(fingerprint, service, route, stack, request_id, user_id, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (fingerprint, service, route, stack, request_id, user_id, event_time),
        )
        row = conn.execute(
            "SELECT count FROM errors WHERE fingerprint = ?", (fingerprint,)
        ).fetchone()

    return fingerprint, row["count"]