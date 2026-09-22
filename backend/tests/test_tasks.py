def _me(client, auth):
    return client.get("/api/v1/auth/me", headers=auth("intern1@internflow.dev")).json()


def test_supervisor_creates_individual_task(client, auth):
    intern = _me(client, auth)
    r = client.post(
        "/api/v1/tasks",
        json={
            "title": "pytest task",
            "description": "created by pytest",
            "scope": "individual",
            "batch_id": 1,
            "assignee_id": intern["id"],
            "category": "Testing",
            "priority": "Medium",
            "deadline": "2030-12-31T23:59:00Z",
        },
        headers=auth("supervisor@internflow.dev"),
    )
    assert r.status_code == 200, r.text
    task = r.json()
    assert task["assignee_id"] == intern["id"]
    return task


def test_intern_cannot_create_tasks(client, auth):
    r = client.post(
        "/api/v1/tasks",
        json={
            "title": "nope",
            "scope": "batch",
            "batch_id": 1,
            "deadline": "2030-12-31T23:59:00Z",
        },
        headers=auth("intern1@internflow.dev"),
    )
    assert r.status_code == 403


def test_submit_review_flow(client, auth):
    task = test_supervisor_creates_individual_task(client, auth)
    tid = task["id"]

    sub = client.post(
        f"/api/v1/submissions/{tid}",
        json={"github_url": "https://github.com/example/pr", "notes": "done by pytest"},
        headers=auth("intern1@internflow.dev"),
    )
    assert sub.status_code in (200, 201), sub.text
    submission_id = sub.json()["id"]

    review = client.post(
        f"/api/v1/submissions/{submission_id}/review",
        json={"decision": "approved", "score": 8.5, "feedback": "looks good"},
        headers=auth("supervisor@internflow.dev"),
    )
    assert review.status_code == 200, review.text
    assert review.json()["decision"] == "approved"

    detail = client.get(f"/api/v1/submissions/{submission_id}", headers=auth("intern1@internflow.dev"))
    assert detail.json()["status"] == "approved"


def test_extension_requires_manage(client, auth):
    intern = _me(client, auth)
    task = test_supervisor_creates_individual_task(client, auth)
    r = client.post(
        f"/api/v1/tasks/{task['id']}/extensions",
        json={
            "task_id": task["id"],
            "intern_id": intern["id"],
            "new_deadline": "2031-01-15T00:00:00Z",
            "reason": "pytest extension",
        },
        headers=auth("supervisor@internflow.dev"),
    )
    assert r.status_code == 200, r.text
    assert r.json()["new_deadline"].startswith("2031")