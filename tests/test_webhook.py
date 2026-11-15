from app.core.config import settings

WEBHOOK_URL = "/api/v1/webhooks/leads"

# Same repeated request is used across tests so the payload hash stays stable.
TEST_DATA = {
    "name": "Webhook Customer",
    "phone": "13800138000",
    "email": "webhook@example.com",
    "company": "Test Company",
    "message": "Customer inquiry submitted through the webhook",
}


def get_headers(idempotency_key: str, secret: str | None = None):
    """Build the webhook headers, defaulting to the configured shared secret."""
    return {
        "X-Webhook-Secret": (
            secret if secret is not None
            else settings.webhook_secret
        ),
        "Idempotency-Key": idempotency_key,
    }


def test_receive_lead_webhook(client):
    response = client.post(
        WEBHOOK_URL,
        headers=get_headers("event-001"),
        json=TEST_DATA,
    )

    assert response.status_code == 201

    result = response.json()

    assert result["name"] == "Webhook Customer"
    assert result["phone"] == "13800138000"
    assert result["status"] == "NEW"


def test_receive_lead_webhook_with_invalid_secret(client):
    response = client.post(
        WEBHOOK_URL,
        headers=get_headers("event-002", secret="wrong-secret"),
        json=TEST_DATA,
    )

    assert response.status_code == 403


def test_receive_lead_webhook_without_secret(client):
    response = client.post(
        WEBHOOK_URL,
        headers={"Idempotency-Key": "event-003"},
        json=TEST_DATA,
    )

    assert response.status_code == 403


def test_receive_lead_webhook_without_idempotency_key(client):
    response = client.post(
        WEBHOOK_URL,
        headers={"X-Webhook-Secret": settings.webhook_secret},
        json=TEST_DATA,
    )

    assert response.status_code == 422


def test_webhook_idempotency_same_key_same_payload(client):
    headers = get_headers("event-004")

    # First delivery creates the lead.
    first_response = client.post(
        WEBHOOK_URL,
        headers=headers,
        json=TEST_DATA,
    )

    assert first_response.status_code == 201

    first_lead = first_response.json()

    # Retry with the same key and the same payload.
    second_response = client.post(
        WEBHOOK_URL,
        headers=headers,
        json=TEST_DATA,
    )

    assert second_response.status_code == 200

    second_lead = second_response.json()

    # Both calls return the same lead.
    assert first_lead["id"] == second_lead["id"]

    # And only one lead exists in the database.
    list_response = client.get("/api/v1/leads?page=1&page_size=100")

    assert list_response.json()["total"] == 1


def test_webhook_idempotency_same_key_different_payload(client):
    headers = get_headers("event-005")

    first_response = client.post(
        WEBHOOK_URL,
        headers=headers,
        json=TEST_DATA,
    )

    assert first_response.status_code == 201

    # Same key, but the customer details changed.
    different_data = {
        **TEST_DATA,
        "name": "Another Customer",
        "phone": "13900139000",
    }

    second_response = client.post(
        WEBHOOK_URL,
        headers=headers,
        json=different_data,
    )

    assert second_response.status_code == 409

    # The conflicting request must not create a second lead.
    list_response = client.get("/api/v1/leads?page=1&page_size=100")

    assert list_response.json()["total"] == 1


def test_webhook_different_keys_create_separate_leads(client):
    first_response = client.post(
        WEBHOOK_URL,
        headers=get_headers("event-006"),
        json=TEST_DATA,
    )

    second_response = client.post(
        WEBHOOK_URL,
        headers=get_headers("event-007"),
        json=TEST_DATA,
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201

    assert first_response.json()["id"] != second_response.json()["id"]


def test_webhook_returns_409_when_original_lead_was_deleted(client):
    headers = get_headers("event-008")

    first_response = client.post(
        WEBHOOK_URL,
        headers=headers,
        json=TEST_DATA,
    )

    assert first_response.status_code == 201

    lead_id = first_response.json()["id"]

    client.delete(f"/api/v1/leads/{lead_id}")

    # The key is still recorded, but its lead is gone.
    second_response = client.post(
        WEBHOOK_URL,
        headers=headers,
        json=TEST_DATA,
    )

    assert second_response.status_code == 409


def test_webhook_rejects_invalid_payload(client):
    response = client.post(
        WEBHOOK_URL,
        headers=get_headers("event-009"),
        json={"name": "Missing phone"},
    )

    assert response.status_code == 422
