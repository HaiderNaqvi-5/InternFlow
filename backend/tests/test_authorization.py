"""Regression tests for the P0 authorization hardening.

These tests assert the resource-level authorization boundaries:
interns, supervisors, and admins can each only reach what the PRD
permits, and the /storage static mount no longer exposes private files.
"""

import io

import pytest


def _make_user_in_db(email: str, role: str, name: str | None = None) -> dict:
    """Create a user directly in the DB so it can log in with the demo password."""
    from app.core.security import hash_password
    from app.db.session import SessionLocal
    from app.models import User, UserRole

    db = SessionLocal()
    try:
        user = User(
            email=email,
            full_name=name or f"Test {role} {email[:6]}",
            role=UserRole(role),
            password_hash=hash_password("Demo1234!"),
            must_reset_password=False,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return {"id": user.id, "email": user.email}
    finally:
        db.close()


def _create_batch_in_db(name: str, supervisor_id: int, capacity: int = 5) -> dict:
    """Create a batch directly in the DB (avoids reset-password flow of created users)."""
    from app.db.session import SessionLocal
    from app.models import Batch

    db = SessionLocal()
    try:
        batch = Batch(
            name=name,
            description="created by authorization tests",
            start_date="2026-01-01",
            end_date="2026-12-31",
            supervisor_id=supervisor_id,
            capacity=capacity,
            start_time="09:00",
            end_time="18:00",
            grace_minutes=20,
            status="active",
        )
        db.add(batch)
        db.commit()
        db.refresh(batch)
        return {"id": batch.id, "name": batch.name}
    finally:
        db.close()


def _login(client, email: str, password: str = "Demo1234!") -> dict:
    r = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert r.status_code == 200, (email, r.text)
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def intern3_auth(client):
    return _login(client, "intern3@internflow.dev")


@pytest.fixture(scope="module")
def admin_auth(client):
    return _login(client, "admin@internflow.dev")


def _intern_me(client, auth, email: str = "intern1@internflow.dev"):
    return client.get("/api/v1/auth/me", headers=auth(email)).json()


# ---------------------------------------------------------------------------
# Private storage must not be publicly reachable
# ---------------------------------------------------------------------------


def test_storage_mount_is_removed(client):
    """Direct /storage URLs must not serve private files anymore."""
    for path in (
        "/storage/submissions/test.zip",
        "/storage/reports/test.pdf",
        "/storage/signatures/signature.png",
        "/storage/certificates/cert.pdf",
        "/storage/uploads/avatar.png",
    ):
        r = client.get(path)
        assert r.status_code == 404, (path, r.status_code)


# ---------------------------------------------------------------------------
# Individual task privacy
# ---------------------------------------------------------------------------


def test_intern_cannot_view_another_interns_individual_task(client, auth, intern3_auth):
    """The seeded individual task is assigned to intern3; intern1 (same batch)
    must not be able to open it."""
    tasks = client.get(
        "/api/v1/tasks?page_size=100", headers=intern3_auth
    ).json()["items"]
    for t in tasks:
        if t["scope"] == "individual":
            as_assignee = client.get(
                f"/api/v1/tasks/{t['id']}", headers=intern3_auth
            )
            assert as_assignee.status_code == 200, as_assignee.text
            other = client.get(
                f"/api/v1/tasks/{t['id']}",
                headers=auth("intern1@internflow.dev"),
            )
            assert other.status_code in (403, 404), other.text


def test_intern_cannot_access_individual_child_resources(client, auth, intern3_auth):
    """Comments/downloads tied to another intern's individual task stay private."""
    tasks = client.get("/api/v1/tasks?page_size=100", headers=intern3_auth).json()["items"]
    indiv_task = next((t for t in tasks if t["scope"] == "individual"), None)
    assert indiv_task is not None
    tid = indiv_task["id"]

    comments = client.get(
        f"/api/v1/tasks/{tid}/comments", headers=auth("intern1@internflow.dev")
    )
    assert comments.status_code in (403, 404), comments.text

    # intern1 cannot comment on intern3's individual task
    r = client.post(
        f"/api/v1/tasks/{tid}/comments",
        json={"content": "nosy"},
        headers=auth("intern1@internflow.dev"),
    )
    assert r.status_code in (403, 404), r.text


def test_batch_task_visible_to_all_batch_interns(client, auth):
    """A BATCH-scoped task is visible to every intern in the batch."""
    tasks = client.get("/api/v1/tasks?page_size=100", headers=auth("intern1@internflow.dev")).json()["items"]
    batch_task = next((t for t in tasks if t["scope"] == "batch"), None)
    assert batch_task is not None
    for email in ("intern1@internflow.dev", "intern2@internflow.dev"):
        r = client.get(f"/api/v1/tasks/{batch_task['id']}", headers=auth(email))
        assert r.status_code == 200, (email, r.text)


# ---------------------------------------------------------------------------
# Submission privacy
# ---------------------------------------------------------------------------


def test_intern_cannot_read_another_interns_submission(client, auth):
    """Seeded sub for task t4 belongs to intern1; intern2 must be denied."""
    subs = client.get("/api/v1/submissions/my", headers=auth("intern1@internflow.dev")).json()
    assert subs, "expected seeded submission for intern1"
    sub_id = subs[0]["id"]

    ok = client.get(f"/api/v1/submissions/{sub_id}", headers=auth("intern1@internflow.dev"))
    assert ok.status_code == 200, ok.text

    denied = client.get(f"/api/v1/submissions/{sub_id}", headers=auth("intern2@internflow.dev"))
    assert denied.status_code in (403, 404), denied.text


def test_intern_cannot_download_another_interns_submission(client, auth):
    subs = client.get("/api/v1/submissions/my", headers=auth("intern1@internflow.dev")).json()
    assert subs
    sub_id = subs[0]["id"]
    r = client.get(
        f"/api/v1/submissions/{sub_id}/download", headers=auth("intern2@internflow.dev")
    )
    # Authorization runs before any file availability check; intern2 must be denied.
    assert r.status_code in (403, 404), r.text


def test_admin_can_view_submission_but_not_review(client, admin_auth, auth):
    subs = client.get("/api/v1/submissions/my", headers=auth("intern1@internflow.dev")).json()
    assert subs
    sub_id = subs[0]["id"]

    view = client.get(f"/api/v1/submissions/{sub_id}", headers=admin_auth)
    assert view.status_code == 200, view.text

    review = client.post(
        f"/api/v1/submissions/{sub_id}/review",
        json={"decision": "approved", "score": 9, "feedback": "admin should not review"},
        headers=admin_auth,
    )
    assert review.status_code == 403, review.text


def test_admin_cannot_grant_deadline_extension(client, admin_auth, auth):
    tasks = client.get("/api/v1/tasks?page_size=100", headers=auth("intern1@internflow.dev")).json()["items"]
    tid = tasks[0]["id"]
    intern = _intern_me(client, auth)
    r = client.post(
        f"/api/v1/tasks/{tid}/extensions",
        json={
            "task_id": tid,
            "intern_id": intern["id"],
            "new_deadline": "2031-01-15T00:00:00Z",
            "reason": "admin test",
        },
        headers=admin_auth,
    )
    assert r.status_code == 403, r.text


def test_admin_cannot_change_academic_deadline(client, admin_auth, auth):
    tasks = client.get("/api/v1/tasks?page_size=100", headers=auth("intern1@internflow.dev")).json()["items"]
    tid = tasks[0]["id"]
    r = client.patch(
        f"/api/v1/tasks/{tid}",
        json={"deadline": "2032-01-01T00:00:00Z"},
        headers=admin_auth,
    )
    assert r.status_code == 403, r.text


# ---------------------------------------------------------------------------
# Supervisor scoping
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def second_supervisor():
    return _make_user_in_db("supb@internflow.dev", "supervisor")


@pytest.fixture(scope="module")
def second_batch(second_supervisor):
    return _create_batch_in_db("Batch B Test", second_supervisor["id"])


def test_supervisor_a_cannot_access_supervisor_b_batch(client, second_supervisor, second_batch):
    sup_a = _login(client, "supervisor@internflow.dev")
    r = client.get(f"/api/v1/batches/{second_batch['id']}", headers=sup_a)
    assert r.status_code == 403, r.text

    sup_b = _login(client, "supb@internflow.dev")
    r = client.get(f"/api/v1/batches/{second_batch['id']}", headers=sup_b)
    assert r.status_code == 200, r.text


def test_supervisor_a_cannot_review_supervisor_b_submission(client, second_batch, admin_auth):
    # intern in batch B creates a submission, supervisor A must be denied
    intern = _make_user_in_db("internb@internflow.dev", "intern")
    add = client.post(
        f"/api/v1/batches/{second_batch['id']}/interns",
        json={"user_id": intern["id"]},
        headers=admin_auth,
    )
    assert add.status_code == 200, add.text

    task = client.post(
        "/api/v1/tasks",
        json={
            "title": "Batch B task",
            "scope": "batch",
            "batch_id": second_batch["id"],
            "deadline": "2030-12-31T23:59:00Z",
        },
        headers=_login(client, "supb@internflow.dev"),
    )
    assert task.status_code == 200, task.text

    sub = client.post(
        f"/api/v1/submissions/{task.json()['id']}",
        json={"github_url": "https://github.com/example/b"},
        headers=_login(client, "internb@internflow.dev"),
    )
    assert sub.status_code in (200, 201), sub.text

    denied = client.post(
        f"/api/v1/submissions/{sub.json()['id']}/review",
        json={"decision": "approved", "score": 5, "feedback": "not my intern"},
        headers=_login(client, "supervisor@internflow.dev"),
    )
    assert denied.status_code == 403, denied.text

    allowed = client.post(
        f"/api/v1/submissions/{sub.json()['id']}/review",
        json={"decision": "approved", "score": 5, "feedback": "fine"},
        headers=_login(client, "supb@internflow.dev"),
    )
    assert allowed.status_code == 200, allowed.text


# ---------------------------------------------------------------------------
# Archived batch read-only
# ---------------------------------------------------------------------------


def test_archived_batch_cannot_be_mutated(client, admin_auth, second_supervisor):
    batch = _create_batch_in_db("Batch Archive Test", second_supervisor["id"])
    intern = _make_user_in_db("internarch@internflow.dev", "intern")
    add = client.post(
        f"/api/v1/batches/{batch['id']}/interns",
        json={"user_id": intern["id"]},
        headers=admin_auth,
    )
    assert add.status_code == 200, add.text

    archive = client.post(f"/api/v1/batches/{batch['id']}/archive", headers=admin_auth)
    assert archive.status_code == 200, archive.text

    # add intern to archived batch (different intern) -> 403
    intern2 = _make_user_in_db("internarch2@internflow.dev", "intern")
    add_after = client.post(
        f"/api/v1/batches/{batch['id']}/interns",
        json={"user_id": intern2["id"]},
        headers=admin_auth,
    )
    assert add_after.status_code == 403, add_after.text

    # create task in archived batch -> 403
    task = client.post(
        "/api/v1/tasks",
        json={
            "title": "late task",
            "scope": "batch",
            "batch_id": batch["id"],
            "deadline": "2030-12-31T23:59:00Z",
        },
        headers=_login(client, "supb@internflow.dev"),
    )
    assert task.status_code == 403, task.text


# ---------------------------------------------------------------------------
# Full authorized download of an intern's own submission file
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Completion outcomes + certificates are scoped per role
# ---------------------------------------------------------------------------


def test_completion_and_certificates_scoped(client, auth, admin_auth):
    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models import Certificate, InternshipOutcome, User

    db = SessionLocal()
    try:
        i2_id = db.execute(
            select(User.id).where(User.email == "intern2@internflow.dev")
        ).scalar_one()
        outcome = InternshipOutcome(
            intern_id=i2_id, batch_id=1, hr_completion_status="completed"
        )
        cert = Certificate(intern_id=i2_id, batch_id=1, filename="i2.pdf")
        db.add_all([outcome, cert])
        db.commit()
        cert_id = cert.id
    finally:
        db.close()

    # intern1 must not see intern2's outcome/certificate
    outcomes = client.get("/api/v1/completions", headers=auth("intern1@internflow.dev")).json()
    certs = client.get("/api/v1/certificates", headers=auth("intern1@internflow.dev")).json()
    assert all(o["intern_id"] != i2_id for o in outcomes)
    assert all(c["intern_id"] != i2_id for c in certs)

    # supervisor (batch 1) and admin do see them
    sup_outcomes = client.get("/api/v1/completions", headers=_login(client, "supervisor@internflow.dev")).json()
    assert any(o["intern_id"] == i2_id for o in sup_outcomes)
    sup_certs = client.get("/api/v1/certificates", headers=_login(client, "supervisor@internflow.dev")).json()
    assert any(c["intern_id"] == i2_id for c in sup_certs)

    admin_outcomes = client.get("/api/v1/completions", headers=admin_auth).json()
    assert any(o["intern_id"] == i2_id for o in admin_outcomes)

    # intern2 can download own certificate; intern1 cannot
    own = client.get(
        f"/api/v1/certificates/{cert_id}/download", headers=auth("intern2@internflow.dev")
    )
    assert own.status_code in (200, 404), own.text  # 404 until file is generated
    denied = client.get(
        f"/api/v1/certificates/{cert_id}/download", headers=auth("intern1@internflow.dev")
    )
    assert denied.status_code == 403, denied.text


def test_intern_downloads_own_submission_file(client, auth):
    task = client.post(
        "/api/v1/tasks",
        json={
            "title": "file submission task",
            "scope": "batch",
            "batch_id": 1,
            "deadline": "2031-06-01T23:59:00Z",
        },
        headers=_login(client, "supervisor@internflow.dev"),
    )
    assert task.status_code == 200, task.text
    tid = task.json()["id"]

    files = {"file": ("work.zip", io.BytesIO(b"PK\x03\x04 fake zip"), "application/zip")}
    r = client.post(
        f"/api/v1/submissions/{tid}/file",
        files=files,
        headers=_login(client, "intern1@internflow.dev"),
    )
    assert r.status_code in (200, 201), r.text
    sub_id = r.json()["id"]

    dl = client.get(
        f"/api/v1/submissions/{sub_id}/download", headers=_login(client, "intern1@internflow.dev")
    )
    assert dl.status_code == 200, dl.text

    denied = client.get(
        f"/api/v1/submissions/{sub_id}/download", headers=_login(client, "intern2@internflow.dev")
    )
    assert denied.status_code in (403, 404), denied.text