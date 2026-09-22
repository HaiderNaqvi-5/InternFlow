def test_audit_admin_only(client, auth):
    assert client.get("/api/v1/audit", headers=auth("supervisor@internflow.dev")).status_code == 403
    r = client.get("/api/v1/audit?page_size=5", headers=auth("admin@internflow.dev"))
    assert r.status_code == 200, r.text
    assert "items" in r.json()


def test_company_settings_admin_only(client, auth):
    assert client.get("/api/v1/company/settings", headers=auth("supervisor@internflow.dev")).status_code == 403
    r = client.get("/api/v1/company/settings", headers=auth("admin@internflow.dev"))
    assert r.status_code == 200, r.text
    assert "company_name" in r.json()


def test_reports_admin_only(client, auth):
    assert client.get(
        "/api/v1/reports/exports/attendance?batch_id=1", headers=auth("supervisor@internflow.dev")
    ).status_code == 403
    ok = client.get("/api/v1/reports/exports/attendance?batch_id=1", headers=auth("admin@internflow.dev"))
    assert ok.status_code == 200, ok.text
    r = client.get("/api/v1/reports?page_size=5", headers=auth("admin@internflow.dev"))
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)


def test_events_and_announcements_supervisor_can_post(client, auth):
    sup = auth("supervisor@internflow.dev")
    ann = client.post(
        "/api/v1/announcements",
        json={"batch_id": 1, "title": "pytest ann", "content": "hello", "is_pinned": False},
        headers=sup,
    )
    assert ann.status_code == 200, ann.text

    evt = client.post(
        "/api/v1/events",
        json={"batch_id": 1, "title": "pytest event", "event_type": "meeting",
              "starts_at": "2030-03-01T10:00:00Z"},
        headers=sup,
    )
    assert evt.status_code == 200, evt.text
    assert evt.json()["event_type"] == "meeting"


def test_search_returns_matches(client, auth):
    r = client.get("/api/v1/search?q=task", headers=auth("intern1@internflow.dev"))
    assert r.status_code == 200
    assert r.json()["query"] == "task"
    assert isinstance(r.json()["results"], list)


def test_notifications_mark_read(client, auth):
    intern = auth("intern1@internflow.dev")
    before = client.get("/api/v1/notifications/unread-count", headers=intern).json()["count"]
    r = client.post("/api/v1/notifications/read", json={"all": True}, headers=intern)
    assert r.status_code == 200, r.text
    after = client.get("/api/v1/notifications/unread-count", headers=intern).json()["count"]
    assert after == 0
    assert before >= 1