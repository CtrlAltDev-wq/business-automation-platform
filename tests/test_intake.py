FORM_URL = "/api/v1/intake/forms"


def test_form_submission_creates_normalized_lead(client):
    response = client.post(
        FORM_URL,
        json={
            "name": "  Alice Chen  ",
            "email": "Alice.Chen@Example.COM",
            "phone": "+86 138-0013-8000",
            "company": "ABC Tech",
            "message": "Please send a quote.",
        },
    )

    assert response.status_code == 201

    body = response.json()

    assert body["duplicate"] is False
    assert body["extracted_fields"] == []

    lead = body["lead"]

    assert lead["name"] == "Alice Chen"
    assert lead["email"] == "alice.chen@example.com"
    assert lead["phone"] == "13800138000"
    assert lead["company"] == "ABC Tech"
    assert lead["status"] == "NEW"


def test_form_extracts_contact_details_from_message(client):
    response = client.post(
        FORM_URL,
        json={
            "name": "Bob",
            "message": "Hi, my email is bob@example.com and my number is +86 139 0013 9000.",
            "budget": "5000 USD",
        },
    )

    assert response.status_code == 201

    body = response.json()

    assert body["lead"]["email"] == "bob@example.com"
    assert body["lead"]["phone"] == "13900139000"
    assert set(body["extracted_fields"]) == {"email", "phone"}

    # Unknown form fields are kept inside the stored message.
    assert "5000 USD" in body["lead"]["message"]


def test_form_duplicate_is_stored_as_follow_up(client):
    payload = {
        "name": "Carol",
        "email": "carol@example.com",
        "phone": "137-0013-7000",
        "message": "First inquiry.",
    }

    first_response = client.post(FORM_URL, json=payload)
    second_response = client.post(
        FORM_URL,
        json={**payload, "phone": "13700137000", "message": "Second inquiry."},
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 200

    first_lead = first_response.json()["lead"]
    second_body = second_response.json()

    assert second_body["duplicate"] is True
    assert second_body["lead"]["id"] == first_lead["id"]

    follow_ups = client.get(
        f"/api/v1/leads/{first_lead['id']}/follow-ups"
    ).json()

    assert len(follow_ups) == 1
    assert "Duplicate submission" in follow_ups[0]["content"]
    assert "Second inquiry." in follow_ups[0]["content"]


def test_form_without_contact_details_returns_422(client):
    response = client.post(
        FORM_URL,
        json={"name": "No Contact", "message": "I would like more information."},
    )

    assert response.status_code == 422


def test_form_name_falls_back_to_email_local_part(client):
    response = client.post(
        FORM_URL,
        json={"email": "jane.doe@example.com", "message": "Email only."},
    )

    assert response.status_code == 201

    body = response.json()

    assert body["lead"]["name"] == "Jane Doe"
    assert body["lead"]["phone"] == ""
    assert "name" in body["extracted_fields"]
