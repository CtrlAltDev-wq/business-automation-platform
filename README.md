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
- Email validation via Pydantic `EmailStr`
- Automatic OpenAPI / Swagger documentation
- Test suite running against an in-memory SQLite database

## Tech Stack

| Layer | Technology |
| --- | --- |
| Web framework | FastAPI |
| ORM | SQLAlchemy 2.0 (typed `Mapped` models) |
| Validation | Pydantic v2 |
| Database | SQLite (configurable via `DATABASE_URL`) |
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
│   │           └── lead.py     # Lead HTTP endpoints
│   ├── core/                   # Placeholder for shared config / security
│   ├── db/
│   │   ├── base.py             # Declarative base
│   │   └── database.py         # Engine, session factory, get_db dependency
│   ├── models/
│   │   ├── lead.py             # Lead ORM model
│   │   └── lead_follow_up.py   # Follow-up ORM model
│   ├── schemas/
│   │   └── lead.py             # Pydantic request / response schemas
│   └── services/
│       └── lead_service.py     # Business logic and queries
├── tests/
│   └── test_lead.py            # API tests
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
| `DATABASE_URL` | `sqlite:///./business.db` | SQLAlchemy database URL |
| `SQL_ECHO` | `false` | Set to `true` to log every SQL statement |

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
```

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
