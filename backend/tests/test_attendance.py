def test_attendance_lifecycle(client, auth):
    intern = auth("intern1@internflow.dev")
    sup = auth("supervisor@internflow.dev")

    check_in = client.post("/api/v1/attendance/check-in", headers=intern)
    assert check_in.status_code == 200, check_in.text

    today = client.get("/api/v1/attendance/today", headers=intern)
    assert today.status_code == 200
    record = today.json()
    assert record and record["check_in"] is not None

    check_out = client.post(
        "/api/v1/attendance/check-out",
        json={"work_done": "pytest done", "next_day_plan": "pytest plan"},
        headers=intern,
    )
    assert check_out.status_code == 200, check_out.text

    summary = client.get("/api/v1/attendance/summary", headers=sup)
    assert summary.status_code == 200

    records = client.get("/api/v1/attendance/records?page_size=10", headers=sup)
    assert records.status_code == 200, records.text
    assert records.json()["total"] >= 1


def test_leave_request_and_approval(client, auth):
    intern_email = "intern1@internflow.dev"

    created = client.post(
        "/api/v1/leave",
        json={
            "start_date": "2030-01-10",
            "end_date": "2030-01-12",
            "reason": "pytest leave",
        },
        headers=auth(intern_email),
    )
    assert created.status_code == 200, created.text
    leave_id = created.json()["id"]
    assert created.json()["status"] == "pending"

    decided = client.post(
        f"/api/v1/leave/{leave_id}/decide",
        json={"approve": True},
        headers=auth("admin@internflow.dev"),
    )
    assert decided.status_code == 200, decided.text
    assert decided.json()["status"] == "approved"