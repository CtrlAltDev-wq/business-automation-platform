from app.core.config import settings
from app.core.constants import (
    EVENT_EMAIL_AUTO_REPLY,
    EVENT_N8N_LEAD_CREATED,
    EVENT_SHEETS_APPEND,
)
from app.services import integration_service

FORM_URL = "/api/v1/intake/forms"


def auth_headers():
    """Operational endpoints reuse the webhook shared secret."""
    return {"X-Webhook-Secret": settings.webhook_secret}


def submit(client, **overrides):
    payload = {
        "name": "Integration Test",
        "email": "integration@example.com",
        "phone": "13500135000",
        "message": "Interested in automation.",
    }
    payload.update(overrides)

    return client.post(FORM_URL, json=payload)


def test_intake_queues_and_delivers_one_event_per_integration(client):
    response = submit(client)

    assert response.status_code == 201
    assert set(response.json()["events_queued"]) == {
        EVENT_SHEETS_APPEND,
        EVENT_EMAIL_AUTO_REPLY,
        EVENT_N8N_LEAD_CREATED,
    }

    events = client.get("/api/v1/integrations/events", headers=auth_headers()).json()

    assert len(events) == 3
    # Adapters without credentials run in dry-run mode, so the first attempt succeeds.
    assert {event["status"] for event in events} == {"SENT"}
    assert {event["attempts"] for event in events} == {0}


def test_integration_endpoints_require_secret(client):
    assert client.get("/api/v1/integrations/events").status_code == 403
    assert client.post("/api/v1/integrations/process").status_code == 403


def test_process_endpoint_is_idempotent_when_nothing_is_pending(client):
    submit(client, email="dryrun@example.com", phone="13400134000")

    result = client.post(
        "/api/v1/integrations/process",
        headers=auth_headers(),
    ).json()

    assert result == {
        "processed": 0,
        "sent": 0,
        "retrying": 0,
        "failed": 0,
    }


def test_failed_event_is_retried_then_failed_permanently(client, monkeypatch):
    def broken_handler(payload):
        raise RuntimeError("n8n is unreachable")

    monkeypatch.setitem(
        integration_service.EVENT_HANDLERS,
        EVENT_N8N_LEAD_CREATED,
        broken_handler,
    )
    # Retry immediately and give the event two attempts in total.
    monkeypatch.setattr(settings, "integration_retry_base_seconds", 0)
    monkeypatch.setattr(settings, "integration_max_attempts", 2)

    submit(client, email="retry@example.com", phone="13300133000")

    # The inline attempt fails and schedules the event for a retry.
    pending = client.get(
        "/api/v1/integrations/events",
        headers=auth_headers(),
        params={"status": "PENDING"},
    ).json()

    assert len(pending) == 1
    assert pending[0]["attempts"] == 1
    assert "RuntimeError" in pending[0]["last_error"]

    second_run = client.post(
        "/api/v1/integrations/process",
        headers=auth_headers(),
    ).json()

    assert second_run["failed"] == 1

    failed = client.get(
        "/api/v1/integrations/events",
        headers=auth_headers(),
        params={"status": "FAILED"},
    ).json()

    assert len(failed) == 1
    assert failed[0]["attempts"] == 2
    assert "RuntimeError" in failed[0]["last_error"]


def test_dashboard_reports_integration_health(client):
    submit(client, email="dashboard@example.com", phone="13200132000")

    summary = client.get("/api/v1/dashboard/summary").json()

    assert summary["integration_events"]["SENT"] == 3
    assert summary["integration_events"]["FAILED"] == 0
    assert summary["integration_events"]["PENDING"] == 0
