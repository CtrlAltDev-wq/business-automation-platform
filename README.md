# Business Automation Platform

A RESTful lead management API built with **FastAPI**, **SQLAlchemy 2.0** and **SQLite**.
It is the first module of a business automation platform that helps small sales teams
capture incoming inquiries, track them through a sales pipeline, and record follow-up
activities.

## Features

- Create, read, update and delete leads (full CRUD)
- Paginated lead list with keyword search, status filter and sorting
- Enum-validated lead status with a guarded state machine:
  `NEW → CONTACTED → QUALIFIED → CONVERTED` (any active stage can move to `LOST`)
- Follow-up notes attached to a lead, returned newest first
- Dashboard summary endpoint: lead / follow-up totals, per-status counters and the five latest follow-ups
- Signed webhook ingestion with idempotency keys (retries never create duplicate leads)
- Email validation via Pydantic `EmailStr`
- Automatic OpenAPI / Swagger documentation
- Test suite running against an in-memory SQLite database

## Tech Stack

| Layer | Technology |
| --- | --- |
| Web framework | FastAPI |
| ORM | SQLAlchemy 2.0 (typed `Mapped` models) |
| Validation | Pydantic v2 |
| Configuration | pydantic-settings (`.env` support) |
| Database | PostgreSQL 17 via `psycopg` (SQLite also supported) |
| Server | Uvicorn |
| Testing | pytest + FastAPI TestClient |

## Project Structure

```
business-automation-platform/
├── app/
│   ├── main.py                 # Application entrypoint and router registration
│   ├── api/
│   │   └── v1/
│   │       ├── router.py       # Version 1 API router
│   │       └── endpoints/
│   │           ├── lead.py     # Lead HTTP endpoints
│   │           ├── dashboard.py # Dashboard statistics endpoint
│   │           └── webhook.py  # Signed lead ingestion endpoint
│   ├── core/
│   │   ├── config.py           # Environment-driven settings (.env)
│   │   ├── constants.py        # Pipeline statuses, transitions and shared constants
│   │   └── security.py         # Webhook shared-secret verification
│   ├── db/
│   │   ├── base.py             # Declarative base
│   │   └── database.py         # Engine, session factory, get_db dependency
│   ├── models/
│   │   ├── lead.py             # Lead ORM model
│   │   ├── lead_follow_up.py   # Follow-up ORM model
│   │   └── webhook_idempotency.py # Processed webhook events
│   ├── schemas/
│   │   ├── lead.py             # Lead request / response schemas
│   │   └── dashboard.py        # Dashboard response schemas
│   └── services/
│       ├── lead_service.py     # Lead business logic and queries
│       └── dashboard_service.py # Dashboard aggregation queries
├── tests/
│   ├── conftest.py             # Shared in-memory database fixture
│   ├── test_lead.py            # Lead API tests
│   ├── test_dashboard.py       # Dashboard API tests
│   └── test_webhook.py         # Webhook ingestion and idempotency tests
├── requirements.txt
└── README.md
```

## Getting Started

### 1. Requirements

- Python 3.10+ (tested on 3.14)

### 2. Installation

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Run the server

```bash
uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`, and the interactive docs at:

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

The SQLite file `business.db` is created automatically on first start.

### 4. Run the tests

```bash
pytest -q
```

## Configuration

Configuration is read from environment variables, so no code changes are needed
between environments.

| Variable | Default | Description |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./business.db` | SQLAlchemy URL, e.g. `postgresql+psycopg://app_user:secret@127.0.0.1:5432/business_automation` |
| `SQL_ECHO` | `false` | Set to `true` to log every SQL statement |
| `WEBHOOK_SECRET` | `dev-secret-change-me` | Shared secret required by `POST /webhooks/leads` |

Copy the template and fill in your own values (`.env` itself is git-ignored):

```bash
cp .env.example .env
```

### PostgreSQL

The project defaults to SQLite for a zero-setup start, but PostgreSQL is the
recommended database. A local instance can be started with Docker:

```bash
docker run -d --name business-automation-postgres \
  -e POSTGRES_DB=business_automation \
  -e POSTGRES_USER=user \
  -e POSTGRES_PASSWORD=password \
  -p 5432:5432 postgres:17
```

Then point `.env` at it:

```bash
DATABASE_URL=postgresql+psycopg://user:password@127.0.0.1:5432/business_automation
```

Special characters in the password must be URL-encoded (for example `!` becomes
`%21`). Tables are created automatically on startup; for schema changes use a
migration tool such as Alembic.

## API Reference

Base path: `/api/v1`

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/leads` | Create a lead |
| `GET` | `/leads` | List leads (`page`, `page_size`, `keyword`, `status`, `sort_by`, `sort_order`) |
| `GET` | `/leads/{lead_id}` | Get a lead by id |
| `PUT` | `/leads/{lead_id}` | Partially update a lead |
| `DELETE` | `/leads/{lead_id}` | Delete a lead and its follow-ups |
| `PATCH` | `/leads/{lead_id}/status` | Move a lead to another pipeline status |
| `POST` | `/leads/{lead_id}/follow-ups` | Add a follow-up note |
| `GET` | `/leads/{lead_id}/follow-ups` | List follow-up notes (newest first) |
| `GET` | `/dashboard/summary` | Dashboard totals, per-status counts and 5 latest follow-ups |
| `POST` | `/webhooks/leads` | Authenticated lead ingestion with idempotency support |

Health check: `GET /health`

### Example

```bash
# Create a lead
curl -X POST http://127.0.0.1:8000/api/v1/leads \
  -H "Content-Type: application/json" \
  -d '{"name":"Alice Chen","phone":"13800138000","email":"alice@example.com","company":"ABC Tech"}'

# Move it forward in the pipeline
curl -X PATCH http://127.0.0.1:8000/api/v1/leads/1/status \
  -H "Content-Type: application/json" \
  -d '{"status":"CONTACTED"}'

# Add a follow-up note
curl -X POST http://127.0.0.1:8000/api/v1/leads/1/follow-ups \
  -H "Content-Type: application/json" \
  -d '{"content":"Called the customer, demo scheduled."}'

# Dashboard statistics
curl http://127.0.0.1:8000/api/v1/dashboard/summary
```

Example dashboard response:

```json
{
  "total_leads": 2,
  "total_follow_ups": 1,
  "status_counts": {
    "NEW": 1,
    "CONTACTED": 1,
    "QUALIFIED": 0,
    "CONVERTED": 0,
    "LOST": 0
  },
  "recent_follow_ups": [
    {
      "id": 1,
      "lead_id": 1,
      "lead_name": "Alice Chen",
      "content": "Called the customer, demo scheduled.",
      "created_at": "2026-11-12T08:30:00"
    }
  ]
}
```

### Webhook Ingestion

External systems (landing pages, form builders, CRM connectors) can push leads to
`POST /api/v1/webhooks/leads`.

| Header | Required | Description |
| --- | --- | --- |
| `X-Webhook-Secret` | yes | Must match `WEBHOOK_SECRET`; otherwise `403` |
| `Idempotency-Key` | yes | Unique id per event, 1–255 chars; protects against retries |
| `Content-Type` | yes | `application/json` |

Response semantics:

| Status | Meaning |
| --- | --- |
| `201 Created` | Lead created by this call |
| `200 OK` | Duplicate delivery: the original lead is returned, nothing is created |
| `403 Forbidden` | Missing or wrong secret |
| `409 Conflict` | Same key reused with a different payload, or its lead was deleted |
| `422 Unprocessable Entity` | Missing header or invalid body |

```bash
curl -X POST http://127.0.0.1:8000/api/v1/webhooks/leads \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: $WEBHOOK_SECRET" \
  -H "Idempotency-Key: evt_20261115_0001" \
  -d '{"name":"Alice Chen","phone":"13800138000","email":"alice@example.com"}'
```

Each request is fingerprinted with a SHA-256 hash of its canonical JSON payload and
stored in `webhook_idempotency` together with the created lead, in a single transaction.
Concurrent retries are resolved by the unique constraint on `idempotency_key`.

### Status Workflow

```
NEW ──► CONTACTED ──► QUALIFIED ──► CONVERTED
 │          │             │
 └──────────┴─────────────┴──► LOST
```

Illegal transitions return `409 Conflict`; unknown status values return `422 Unprocessable Entity`.

## Roadmap

- [ ] Authentication and role-based permissions
- [ ] Alembic database migrations
- [ ] Customer and deal modules
- [ ] Background jobs for email / notification automation
- [ ] Docker image and CI pipeline

## License

This project is available for portfolio and demonstration purposes.
