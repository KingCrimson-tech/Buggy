# Buggy

A tiny, self-hosted error tracker: a 3-line Python SDK, a FastAPI ingest API that groups duplicate errors by fingerprint, SQLite storage, and a zero-build dashboard.

No SaaS, no Prometheus, no Grafana, no OTEL. Just the tool itself.

## Architecture

```
  ┌────────────────┐   POST /api/events   ┌───────────────────┐
  │  demo app      │ ───────────────────► │  Buggy API :8000  │
  │  :8001         │                      │  FastAPI          │
  │  + sdk/buggy.py│                      └─────────┬─────────┘
  └────────────────┘                                │ sqlite3
                                          ┌─────────▼─────────┐
                                          │    buggy.db       │
                                          └─────────┬─────────┘
                                                    │ GET /api/*
  ┌────────────────┐        GET /        ┌──────────▼────────┐
  │    Browser     │ ◄────────────────── │  public/ dashboard│
  └────────────────┘                     └───────────────────┘
```

## Quickstart

```bash
docker compose up --build
```

- Dashboard + API: <http://localhost:8000>
- Demo app: <http://localhost:8001/ok>
- API docs: <http://localhost:8000/docs>

Data lives in the `buggy_data` Docker volume. Reset everything with:

```bash
docker compose down -v
```

## Ports

| Port | Service | Purpose |
|------|---------|---------|
| 8000 | `buggy` | Ingest API, query API, dashboard, `/docs` |
| 8001 | `demo` | Demo FastAPI app that reports its own exceptions |

## Demo script

The demo app fails on purpose. Each failing request returns `500` **and** is reported to Buggy:

```bash
# 1. Two different users, same error shape → ONE group, count=2
curl -s http://localhost:8001/user-fail/1
curl -s http://localhost:8001/user-fail/2

# 2. Different message → its own group
curl -s 'http://localhost:8001/fail?msg=Order%20exploded'

# 3. Confirm from the API
curl -s http://localhost:8000/api/errors
curl -s http://localhost:8000/api/stats
```

Open <http://localhost:8000> and click the `Payment failed for order` row to see both events with their stacks.

## Use the SDK in any Python app

```python
from sdk.buggy import init, capture_exception

init(dsn="http://localhost:8000/api/events", service="demo-api")

try:
    checkout()
except Exception as exc:
    capture_exception(exc, route="POST /checkout", user_id="u_42")
```

Optional helpers:

```python
from sdk.buggy import handle_exception, install_excepthook

@handle_exception(route="POST /checkout")
def checkout():
    ...

install_excepthook()  # report uncaught crashes
```

The SDK only depends on `requests` + the standard library. It never raises: a dead or slow Buggy server returns `None`.

## API

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/events` | Ingest one event; returns `202 {fingerprint, count}` |
| `GET` | `/api/errors?search=&service=&limit=50` | List groups, newest first |
| `GET` | `/api/errors/{fingerprint}?events_limit=20` | One group + its latest raw events (`404` if unknown) |
| `GET` | `/api/stats` | `{total_groups, total_events, events_today}` |
| `GET` | `/health` | `{ok: true}` |
| `GET` | `/` | Dashboard |
| `GET` | `/docs` | OpenAPI UI |

Invalid payloads are rejected with `422`; the ingest endpoint never returns `500` for bad SDK input.

## How grouping works

Every error gets a stable 16-character fingerprint:

1. **Normalize the message** — digits → `*`, single/double quoted values → `'*'`/`"*"`, collapse whitespace, truncate to 500 chars. Case is preserved.
2. **Extract frames** — keep the first 3 lines containing `File "`, mask `, line 123` → `, line *`, join with `|`.
3. **Hash** — `sha1(f"{service}|{normalized}|{frames}")[:16]`.

So these two events group together:

```
Payment failed for order 101          Payment failed for order 202
  File "app.py", line 42, in pay        File "app.py", line 99, in pay
```

while a different message, service, or call site creates a new group. The first message seen is kept as the group title; every raw occurrence is stored separately in `events`.

## Dashboard

- Three stat cards: groups, total events, events today
- Debounced message search + service filter
- Table: count, message, service, last seen
- Click a row to open the detail drawer: metadata, stack trace, and every captured event
- Chart.js bar chart of the last 7 days, computed client-side

> **Screenshot placeholder** — drop a screenshot at `docs/dashboard.png` and embed it here:
>
> ```markdown
> ![Buggy dashboard](docs/dashboard.png)
> ```

## Configuration

| Variable | Default | Used by |
|----------|---------|---------|
| `BUGGY_DB` | `buggy.db` | API/database path |
| `BUGGY_DSN` | `http://localhost:8000/api/events` | Demo app SDK target |

## Local development (no Docker)

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# terminal 1
.venv/bin/uvicorn app.main:app --port 8000 --reload

# terminal 2
.venv/bin/uvicorn demo.app:app --port 8001 --reload
```

Run the SDK directly:

```bash
.venv/bin/python -c "
from sdk.buggy import init, capture_exception
init(dsn='http://localhost:8000/api/events', service='my-api')
try:
    raise ValueError('Payment failed for order 123')
except Exception as e:
    print(capture_exception(e, route='POST /checkout'))
"
```

## Project layout

```
app/        FastAPI app, SQLite layer, Pydantic models
sdk/buggy.py   dependency-free-ish client (requests + stdlib)
demo/app.py    FastAPI demo on :8001 that reports real exceptions
public/     vanilla HTML/CSS/JS dashboard (Chart.js via CDN)
Dockerfile  one image, two services via command override
docker-compose.yml
```