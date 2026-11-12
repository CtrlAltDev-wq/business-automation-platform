import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.database import get_db
from app.main import app

# In-memory test database shared across connections by StaticPool.
test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    bind=test_engine,
    autoflush=False,
    autocommit=False,
)


@pytest.fixture
def client():
    """Provide a TestClient wired to a fresh in-memory database for each test."""
    # Create tables before the test and drop them afterwards.
    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    # Replace the production database dependency with the test one.
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    # Clean up data and dependency overrides.
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)


def create_sample_lead(client, **overrides):
    """Helper that creates a lead and returns the parsed response body."""
    payload = {
        "name": "Alice Chen",
        "phone": "13800138000",
        "email": "alice@example.com",
        "company": "ABC Tech",
        "message": "Interested in the automation system",
    }
    payload.update(overrides)

    response = client.post("/api/v1/leads", json=payload)
    assert response.status_code == 201
    return response.json()


def test_create_lead(client):
    body = create_sample_lead(client)

    assert body["id"] == 1
    assert body["name"] == "Alice Chen"
    assert body["status"] == "NEW"


def test_create_lead_rejects_invalid_email(client):
    response = client.post(
        "/api/v1/leads",
        json={"name": "Alice", "phone": "13800138000", "email": "not-an-email"},
    )

    assert response.status_code == 422


def test_get_lead_list(client):
    create_sample_lead(client)

    response = client.get("/api/v1/leads")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["name"] == "Alice Chen"
    assert body["page"] == 1
    assert body["page_size"] == 10


def test_get_lead_list_filters_by_keyword_and_status(client):
    create_sample_lead(client)
    create_sample_lead(client, name="Bob Wang", phone="13900139000", company="XYZ Ltd")

    keyword_response = client.get("/api/v1/leads", params={"keyword": "XYZ"})
    assert keyword_response.status_code == 200
    assert keyword_response.json()["total"] == 1
    assert keyword_response.json()["items"][0]["name"] == "Bob Wang"

    status_response = client.get("/api/v1/leads", params={"status": "NEW"})
    assert status_response.json()["total"] == 2

    lost_response = client.get("/api/v1/leads", params={"status": "LOST"})
    assert lost_response.json()["total"] == 0


def test_get_lead_list_paginates(client):
    for index in range(3):
        create_sample_lead(client, name=f"Lead {index}", phone=f"1380013800{index}")

    response = client.get("/api/v1/leads", params={"page": 2, "page_size": 2})

    body = response.json()
    assert body["total"] == 3
    assert body["pages"] == 2
    assert len(body["items"]) == 1


def test_update_lead(client):
    lead = create_sample_lead(client)

    response = client.put(f"/api/v1/leads/{lead['id']}", json={"name": "Alice Zhang"})

    assert response.status_code == 200
    assert response.json()["name"] == "Alice Zhang"
    # Fields omitted from the payload are left unchanged.
    assert response.json()["phone"] == "13800138000"


def test_delete_lead(client):
    lead = create_sample_lead(client)

    response = client.delete(f"/api/v1/leads/{lead['id']}")

    assert response.status_code == 200
    assert client.get(f"/api/v1/leads/{lead['id']}").status_code == 404


def test_get_nonexistent_lead(client):
    response = client.get("/api/v1/leads/999")

    assert response.status_code == 404


def test_update_lead_status(client):
    lead = create_sample_lead(client)

    response = client.patch(
        f"/api/v1/leads/{lead['id']}/status",
        json={"status": "CONTACTED"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "CONTACTED"


def test_update_lead_status_rejects_invalid_transition(client):
    lead = create_sample_lead(client)

    # NEW can only move to CONTACTED or LOST, so jumping to QUALIFIED is invalid.
    response = client.patch(
        f"/api/v1/leads/{lead['id']}/status",
        json={"status": "QUALIFIED"},
    )

    assert response.status_code == 409


def test_update_lead_status_rejects_unknown_status(client):
    lead = create_sample_lead(client)

    response = client.patch(
        f"/api/v1/leads/{lead['id']}/status",
        json={"status": "ARCHIVED"},
    )

    assert response.status_code == 422


def test_update_lead_status_returns_404_for_missing_lead(client):
    response = client.patch("/api/v1/leads/999/status", json={"status": "CONTACTED"})

    assert response.status_code == 404


def test_create_and_list_follow_ups(client):
    lead = create_sample_lead(client)

    create_response = client.post(
        f"/api/v1/leads/{lead['id']}/follow-ups",
        json={"content": "Called the customer, demo scheduled."},
    )

    assert create_response.status_code == 201
    assert create_response.json()["lead_id"] == lead["id"]

    client.post(
        f"/api/v1/leads/{lead['id']}/follow-ups",
        json={"content": "Sent the proposal."},
    )

    list_response = client.get(f"/api/v1/leads/{lead['id']}/follow-ups")

    assert list_response.status_code == 200
    contents = [item["content"] for item in list_response.json()]
    # Newest follow-up comes first.
    assert contents == ["Sent the proposal.", "Called the customer, demo scheduled."]


def test_create_follow_up_returns_404_for_missing_lead(client):
    response = client.post(
        "/api/v1/leads/999/follow-ups",
        json={"content": "No such lead."},
    )

    assert response.status_code == 404


def test_deleting_lead_removes_its_follow_ups(client):
    lead = create_sample_lead(client)
    client.post(
        f"/api/v1/leads/{lead['id']}/follow-ups",
        json={"content": "First note."},
    )

    client.delete(f"/api/v1/leads/{lead['id']}")

    assert client.get(f"/api/v1/leads/{lead['id']}/follow-ups").status_code == 404
