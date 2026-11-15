# Business Automation Platform

[![CI](https://github.com/CtrlAltDev-wq/business-automation-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/CtrlAltDev-wq/business-automation-platform/actions/workflows/ci.yml)

A business automation platform built with **FastAPI**, **SQLAlchemy 2.0**, **PostgreSQL**
and **n8n**. It helps small sales teams capture incoming inquiries from website forms and
webhooks, clean up contact data, track leads through a sales pipeline, and fan new leads
out to Google Sheets, email auto-replies and n8n workflows with reliable retries.

## Features

- Website form intake: `POST /intake/forms` turns a raw form post into a lead
- Contact extraction: missing email / phone / name are recovered from the free-text
  message (supports `+86`, spaces and dashes in phone numbers)
- Duplicate detection: an existing email or phone stores the submission as a follow-up
  note instead of creating a second lead
- Reliable outbound integrations via a transactional outbox (`integration_events`):
  one event per target, attempted inline and retried by a worker with exponential backoff
- Google Sheets sync (`values:append`), SMTP email auto-reply and n8n webhook trigger
- Every integration degrades to a logged dry-run when its credentials are not configured
- Signed webhook ingestion with idempotency keys (retries never create duplicate leads)
- Create, read, update and delete leads (full CRUD)
- Paginated lead list with keyword search, status filter and sorting
- Enum-validated lead status with a guarded state machine:
  `NEW → CONTACTED → QUALIFIED → CONVERTED` (any active stage can move to `LOST`)
- Follow-up notes attached to a lead, returned newest first
- Dashboard summary endpoint: lead / follow-up totals, per-status counters, integration
  event counters and the five latest follow-ups
- Structured logging (`timestamp | level | logger | message`) to stdout
- Email validation via Pydantic `EmailStr`
- Versioned database schema with Alembic migrations
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
| Migrations | Alembic |
| Integrations | n8n webhooks, Google Sheets API v4, SMTP email |
| HTTP client | httpx / google-auth |
| Server | Uvicorn |
| Testing | pytest + FastAPI TestClient |
| Linting | Ruff |

## Project Structure

```
business-automation-platform/
├── app/
│   ├── main.py                 # Application entrypoint and router registration
│   ├── api/
│   │   └── v1/
│   │       ├── router.py       # Version 1 API router
│   │       └── endpoints/
│   │           ├── lead.py         # Lead HTTP endpoints
│   │           ├── dashboard.py    # Dashboard statistics endpoint
│   │           ├── intake.py       # Website form intake endpoint
│   │           ├── integrations.py # Outbox inspection and manual retry
│   │           └── webhook.py      # Signed lead ingestion endpoint
│   ├── core/
│   │   ├── config.py           # Environment-driven settings (.env)
│   │   ├── constants.py        # Pipeline statuses, event types and shared constants
│   │   ├── logging.py          # Structured stdout logging
│   │   └── security.py         # Webhook shared-secret verification
│   ├── db/
│   │   ├── base.py             # Declarative base
│   │   └── database.py         # Engine, session factory, get_db dependency
│   ├── models/
│   │   ├── lead.py             # Lead ORM model
│   │   ├── lead_follow_up.py   # Follow-up ORM model
│   │   ├── integration_event.py # Outbox for outbound integration events
│   │   └── webhook_idempotency.py # Processed webhook events
│   ├── schemas/
│   │   ├── lead.py             # Lead request / response schemas
│   │   ├── dashboard.py        # Dashboard response schemas
│   │   ├── intake.py           # Form submission schemas
│   │   └── integration.py      # Integration event schemas
│   ├── services/
│   │   ├── lead_service.py     # Lead business logic and queries
│   │   ├── intake_service.py   # Normalisation, extraction and deduplication
│   │   ├── integration_service.py # Outbox queue, dispatch and retry policy
│   │   ├── dashboard_service.py # Dashboard aggregation queries
│   │   └── integrations/
│   │       ├── sheets.py       # Google Sheets append adapter
│   │       ├── mailer.py       # SMTP auto-reply adapter
│   │       └── n8n.py          # n8n webhook adapter
│   └── workers/
│       └── integration_worker.py # Retry worker for pending events
├── alembic/
│   ├── env.py                  # Alembic environment (reads DATABASE_URL from settings)
│   ├── script.py.mako          # Migration file template
│   └── versions/               # Migration scripts
├── alembic.ini                 # Alembic configuration
├── ruff.toml                   # Lint configuration
├── .github/
│   └── workflows/
│       └── ci.yml              # Ruff + migration check + pytest
├── tests/
│   ├── conftest.py             # Shared in-memory database fixture
│   ├── test_lead.py            # Lead API tests
│   ├── test_dashboard.py       # Dashboard API tests
│   ├── test_webhook.py         # Webhook ingestion and idempotency tests
│   ├── test_intake.py          # Form intake, extraction and dedup tests
│   └── test_integrations.py    # Outbox queueing, retry and counters tests
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

### 3. Apply migrations

The schema is managed by Alembic, so create the tables before the first start:

```bash
alembic upgrade head
```

### 4. Run the server

```bash
uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`, and the interactive docs at:

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

### 5. Run the tests

```bash
ruff check .
pytest -q
```

## Continuous Integration

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs on every push to `main` and on
every pull request:

| Step | Command | Purpose |
| --- | --- | --- |
| Lint | `ruff check .` | Style, import order and common bug patterns |
| Verify migrations | `alembic upgrade head` + `alembic check` | Schema builds, models and migrations agree |
| Test | `pytest -q` | 38 API tests against in-memory SQLite |

The lint rules live in `ruff.toml`: `E`, `F`, `W`, `I` and `B`, line length 100, with
`B008` ignored because FastAPI dependency injection calls `Depends()` in argument defaults.
`alembic/versions` is excluded from linting because those files are generated.

The migration step runs against a throwaway SQLite database (`DATABASE_URL=sqlite:///./ci.db`),
so no PostgreSQL service is required. `alembic check` fails the build when a model change
was not turned into a migration.

## Configuration

Configuration is read from environment variables, so no code changes are needed
between environments.

| Variable | Default | Description |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./business.db` | SQLAlchemy URL, e.g. `postgresql+psycopg://app_user:secret@127.0.0.1:5432/business_automation` |
| `SQL_ECHO` | `false` | Set to `true` to log every SQL statement |
| `WEBHOOK_SECRET` | `dev-secret-change-me` | Shared secret required by `POST /webhooks/leads` and `/integrations/*` |
| `INTEGRATIONS_ENABLED` | `true` | Master switch for the outbound automation queue |
| `INTEGRATION_MAX_ATTEMPTS` | `5` | Delivery attempts before an event is marked `FAILED` |
| `INTEGRATION_RETRY_BASE_SECONDS` | `30` | Base delay; backoff is 30s, 60s, 120s, ... |
| `N8N_WEBHOOK_URL` | – | n8n Webhook node URL; empty means dry-run |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | – | Path to the Google service-account JSON key |
| `GOOGLE_SHEETS_SPREADSHEET_ID` | – | Target spreadsheet id |
| `GOOGLE_SHEETS_RANGE` | `Leads!A:H` | Sheet range used by `values:append` |
| `SMTP_HOST` | – | SMTP server; empty means the auto-reply is only logged |
| `SMTP_PORT` | `587` | SMTP port |
| `SMTP_USERNAME` / `SMTP_PASSWORD` | – | SMTP credentials |
| `SMTP_FROM` | `noreply@example.com` | Sender address |
| `SMTP_USE_TLS` | `true` | Use STARTTLS |
| `AUTO_REPLY_SUBJECT` / `AUTO_REPLY_BODY` | see `.env.example` | Auto-reply template; `{name}` is replaced by the lead name |

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
`%21`). The schema is created by Alembic, not by the application.

### Database Migrations

Alembic reads `DATABASE_URL` from the same settings as the application, so `.env`
is the single source of truth.

```bash
alembic upgrade head                    # apply all migrations
alembic revision --autogenerate -m "add customer table"  # generate a migration from model changes
alembic downgrade -1                    # roll back the last migration
alembic check                           # fail if models and migrations are out of sync
alembic current                         # show the applied revision
```

An existing database that was created before Alembic (for example by an earlier
`create_all`) already has the tables. Mark it as up to date instead of re-running
the initial migration:

```bash
alembic stamp head
```

### Docker Compose

The whole stack starts with one command:

```bash
docker compose up --build
```

| Service | Host address | Notes |
| --- | --- | --- |
| API | `http://127.0.0.1:8000` | Swagger UI at `/docs` |
| Worker | – | Runs `integration_worker` in a retry loop |
| Migrate | – | Runs `alembic upgrade head` once, then exits |
| PostgreSQL | `127.0.0.1:5433` | Port 5433 avoids clashing with a local PostgreSQL on 5432 |
| n8n | `http://127.0.0.1:5679` | Port 5679 avoids clashing with a local n8n on 5678 |

The stack starts `migrate` first: it applies the Alembic migrations and exits, and
both `api` and `worker` wait for it to complete successfully
(`service_completed_successfully`). PostgreSQL and n8n data live in named volumes
(`postgres_data`, `n8n_data`), so they survive `docker compose down`.

The API container reads `WEBHOOK_SECRET` from the local `.env` through compose
variable substitution. `N8N_WEBHOOK_URL` defaults to
`http://host.docker.internal:5678/webhook/lead-created` so containers can reach a
local n8n; override it with `N8N_WEBHOOK_URL_DOCKER` (for example
`http://n8n:5678/webhook/lead-created` when n8n runs in this compose network, or an
empty value for dry-run). Inside compose, `127.0.0.1` refers to the container
itself, not the host.

Useful commands:

```bash
docker compose logs -f api        # API logs
docker compose logs -f worker     # retry worker logs
docker compose exec db psql -U app_user -d business_automation -c '\dt'
docker compose down               # stop, keep data
docker compose down -v            # stop and delete volumes
```

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
| `POST` | `/intake/forms` | Convert a raw website form submission into a lead |
| `GET` | `/dashboard/summary` | Dashboard totals, status counters, integration counters and 5 latest follow-ups |
| `POST` | `/webhooks/leads` | Authenticated lead ingestion with idempotency support |
| `POST` | `/integrations/process` | Deliver all due outbound events now (manual retry) |
| `GET` | `/integrations/events` | Inspect outbound events (`status`, `limit`) |

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
  "integration_events": {
    "PENDING": 0,
    "SENT": 3,
    "FAILED": 0
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

### Website Form Intake

`POST /api/v1/intake/forms` accepts a raw form payload. All fields except a contact
method are optional, and unknown fields (extra form widgets) are allowed.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/intake/forms \
  -H "Content-Type: application/json" \
  -d '{"name":"","email":"","message":"Hi, I am Alice, alice@example.com, 138 0013 8000","source":"landing_page"}'
```

The intake pipeline:

1. **Normalise** – emails are lower-cased and validated; phone numbers lose spaces,
   dashes and the `+86` / `0086` prefix.
2. **Extract** – any contact detail missing from the form is recovered from the
   message and from extra fields (`Regex` for email and phone; the email local part
   becomes the name when no name is given).
3. **Deduplicate** – an existing email or phone stores the submission as a follow-up
   note and returns `200` with `"duplicate": true` instead of creating a lead.
4. **Queue automations** – three outbox events are written in the same transaction:
   Google Sheets append, email auto-reply and the n8n `lead.created` webhook.

A submission without any recoverable email or phone returns `422 Unprocessable Entity`.

### Outbound Integrations

New leads fan out through a transactional outbox table (`integration_events`), which
makes delivery reliable without a message broker:

| Event type | Adapter | Target |
| --- | --- | --- |
| `sheets.append_lead` | `services/integrations/sheets.py` | Google Sheets `values:append` |
| `email.auto_reply` | `services/integrations/mailer.py` | SMTP auto-reply to the lead |
| `n8n.lead_created` | `services/integrations/n8n.py` | `POST {"event":"lead.created","data":{...}}` |

Event lifecycle: `PENDING → SENT`, or `PENDING → FAILED` after
`INTEGRATION_MAX_ATTEMPTS` failures. Retries use exponential backoff
(30s, 60s, 120s, ...) stored in `next_retry_at`. Any adapter whose credentials are
missing runs in dry-run mode and is recorded as sent, so the demo works with an
empty `.env`.

```bash
# Inspect recent events (including failures and their last_error)
curl -H "X-Webhook-Secret: $WEBHOOK_SECRET" \
  "http://127.0.0.1:8000/api/v1/integrations/events?status=PENDING&limit=20"

# Deliver due events right now (manual retry)
curl -X POST -H "X-Webhook-Secret: $WEBHOOK_SECRET" \
  http://127.0.0.1:8000/api/v1/integrations/process
```

The first delivery attempt happens inline in the request; later retries are handled by
the worker:

```bash
# Process due events once and exit
python -m app.workers.integration_worker --once

# Run continuously, polling every 15 seconds (the default)
python -m app.workers.integration_worker --interval 15
```

### Status Workflow

```
NEW ──► CONTACTED ──► QUALIFIED ──► CONVERTED
 │          │             │
 └──────────┴─────────────┴──► LOST
```

Illegal transitions return `409 Conflict`; unknown status values return `422 Unprocessable Entity`.

## Roadmap

- [x] Background retry worker for email / Sheets / n8n automation
- [x] Docker Compose stack (API + worker + PostgreSQL + n8n)
- [x] Alembic database migrations
- [x] CI pipeline (ruff + pytest)
- [ ] Authentication and role-based permissions
- [ ] Customer and deal modules

## License

This project is available for portfolio and demonstration purposes.
