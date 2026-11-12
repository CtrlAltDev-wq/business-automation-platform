from app.core.constants import LEAD_STATUSES


def test_dashboard_summary(client):
    # 1. Create the first lead.
    response1 = client.post(
        "/api/v1/leads",
        json={
            "name": "Alice Chen",
            "phone": "13800138000",
        },
    )

    assert response1.status_code == 201

    lead1_id = response1.json()["id"]

    # 2. Create a second lead.
    response2 = client.post(
        "/api/v1/leads",
        json={
            "name": "Bob Wang",
            "phone": "13800138001",
        },
    )

    assert response2.status_code == 201

    lead2_id = response2.json()["id"]

    # 3. Move the second lead to CONTACTED.
    status_response = client.patch(
        f"/api/v1/leads/{lead2_id}/status",
        json={
            "status": "CONTACTED",
        },
    )

    assert status_response.status_code == 200

    # 4. Add a follow-up note to the first lead.
    follow_up_response = client.post(
        f"/api/v1/leads/{lead1_id}/follow-ups",
        json={
            "content": "First phone call, the customer is interested.",
        },
    )

    assert follow_up_response.status_code == 201

    # 5. Query the dashboard summary.
    dashboard_response = client.get("/api/v1/dashboard/summary")

    assert dashboard_response.status_code == 200

    result = dashboard_response.json()

    # 6. Verify the aggregated counters.
    assert result["total_leads"] == 2
    assert result["total_follow_ups"] == 1

    assert result["status_counts"]["NEW"] == 1
    assert result["status_counts"]["CONTACTED"] == 1
    assert result["status_counts"]["QUALIFIED"] == 0

    # 7. Verify the recent follow-ups.
    assert len(result["recent_follow_ups"]) == 1

    recent = result["recent_follow_ups"][0]

    assert recent["lead_id"] == lead1_id
    assert recent["lead_name"] == "Alice Chen"
    assert recent["content"] == "First phone call, the customer is interested."


def test_dashboard_summary_on_empty_database(client):
    response = client.get("/api/v1/dashboard/summary")

    assert response.status_code == 200

    result = response.json()

    assert result["total_leads"] == 0
    assert result["total_follow_ups"] == 0
    assert result["recent_follow_ups"] == []
    # Every pipeline stage is still reported, with a zero count.
    assert result["status_counts"] == {status: 0 for status in LEAD_STATUSES}


def test_dashboard_shows_latest_five_follow_ups(client):
    lead = client.post(
        "/api/v1/leads",
        json={"name": "Alice Chen", "phone": "13800138000"},
    ).json()

    for index in range(6):
        client.post(
            f"/api/v1/leads/{lead['id']}/follow-ups",
            json={"content": f"Note {index}"},
        )

    response = client.get("/api/v1/dashboard/summary")

    assert response.status_code == 200

    recent_follow_ups = response.json()["recent_follow_ups"]

    # Only the five newest notes are returned, newest first.
    assert len(recent_follow_ups) == 5
    assert [item["content"] for item in recent_follow_ups] == [
        "Note 5",
        "Note 4",
        "Note 3",
        "Note 2",
        "Note 1",
    ]
