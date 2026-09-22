"""Workflow-integrity regression tests (hardening plan item 23)."""

from datetime import date, datetime, time, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import AttendanceRecord, Batch, LeaveRequest, User, UserRole


def _unique_suffix() -> str:
    return uuid4().hex[:8]


def _make_user_in_db(email: str, role: str, name: str | None = None) -> dict:
    """Create a user directly in the DB so it can log in with the demo password."""
    email = f"{email.split('@')[0]}-{_unique_suffix()}@internflow.dev"
    db = SessionLocal()
    try:
        user = User(
            email=email,
            full_name=name or f"Workflow {role} {email[:6]}",
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


def _create_batch_in_db(name: str, supervisor_id: int, capacity: int = 10) -> dict:
    db = SessionLocal()
    try:
        batch = Batch(
            name=f"{name}-{_unique_suffix()}",
            description="created by workflow tests",
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


@pytest.fixture
def sup(client):
    return _login(client, "supervisor@internflow.dev")


@pytest.fixture
def admin(client):
    return _login(client, "admin@internflow.dev")


@pytest.fixture
def intern1(client):
    return _login(client, "intern1@internflow.dev")


@pytest.fixture
def intern2(client):
    return _login(client, "intern2@internflow.dev")


def _task_deadline(days_from_now: int) -> str:
    day = date.today() + timedelta(days=days_from_now)
    return datetime.combine(day, time(17, 0)).isoformat() + "Z"


def _create_batch_task(client, sup, deadline_days, title):
    r = client.post(
        "/api/v1/tasks",
        json={
            "title": title,
            "scope": "batch",
            "batch_id": 1,
            "deadline": _task_deadline(deadline_days),
        },
        headers=sup,
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _sup_id(db):
    return db.execute(
        select(User.id).where(User.email == "supervisor@internflow.dev")
    ).scalar_one()


# ---------------------------------------------------------------------------
# Deadline extensions: individual scope, used in lateness calc
# ---------------------------------------------------------------------------


def test_extension_affects_one_intern_only(client, sup, intern1, intern2):
    tid = _create_batch_task(client, sup, -1, "extension-lateness task")

    me = client.get("/api/v1/auth/me", headers=intern1).json()
    ext = client.post(
        f"/api/v1/tasks/{tid}/extensions",
        json={
            "task_id": tid,
            "intern_id": me["id"],
            "new_deadline": _task_deadline(7),
            "reason": "workflow test",
        },
        headers=sup,
    )
    assert ext.status_code == 200, ext.text

    sub_a = client.post(
        f"/api/v1/submissions/{tid}",
        json={"github_url": "https://github.com/a/work"},
        headers=intern1,
    )
    assert sub_a.status_code in (200, 201), sub_a.text
    assert sub_a.json()["is_late"] is False, "intern1 has extension, must be on time"

    sub_b = client.post(
        f"/api/v1/submissions/{tid}",
        json={"github_url": "https://github.com/b/work"},
        headers=intern2,
    )
    assert sub_b.status_code in (200, 201), sub_b.text
    assert sub_b.json()["is_late"] is True, "intern2 has no extension, must be late"


def test_extension_target_must_be_batch_member(client, sup):
    tid = _create_batch_task(client, sup, 10, "extension member check task")
    outsider = _make_user_in_db("workflow-outsider@internflow.dev", "intern")

    r = client.post(
        f"/api/v1/tasks/{tid}/extensions",
        json={
            "task_id": tid,
            "intern_id": outsider["id"],
            "new_deadline": _task_deadline(20),
            "reason": "should fail",
        },
        headers=sup,
    )
    assert r.status_code == 400, r.text


# ---------------------------------------------------------------------------
# Submission version history is append-only
# ---------------------------------------------------------------------------


def test_submission_versions_are_preserved(client, sup, intern1):
    tid = _create_batch_task(client, sup, 15, "version history task")

    v1 = client.post(
        f"/api/v1/submissions/{tid}",
        json={"github_url": "https://github.com/a/v1", "notes": "first attempt"},
        headers=intern1,
    )
    assert v1.status_code in (200, 201), v1.text
    v1_id = v1.json()["id"]

    rev = client.post(
        f"/api/v1/submissions/{v1_id}/review",
        json={"decision": "changes_requested", "score": 6, "feedback": "please revise"},
        headers=sup,
    )
    assert rev.status_code == 200, rev.text

    v2 = client.post(
        f"/api/v1/submissions/{tid}",
        json={"github_url": "https://github.com/a/v1", "notes": "second attempt"},
        headers=intern1,
    )
    assert v2.status_code in (200, 201), v2.text
    v2_id = v2.json()["id"]

    assert v1_id != v2_id
    assert v2.json()["version"] == 2

    v1_detail = client.get(f"/api/v1/submissions/{v1_id}", headers=sup)
    assert v1_detail.status_code == 200, v1_detail.text
    assert len(v1_detail.json()["reviews"]) == 1
    assert v1_detail.json()["reviews"][0]["feedback"] == "please revise"


# ---------------------------------------------------------------------------
# Review validation (score + feedback mandatory)
# ---------------------------------------------------------------------------


def test_review_validation(client, sup, intern1):
    tid = _create_batch_task(client, sup, 15, "review validation task")
    sub = client.post(
        f"/api/v1/submissions/{tid}",
        json={"github_url": "https://github.com/a/revv"},
        headers=intern1,
    )
    assert sub.status_code in (200, 201), sub.text
    sub_id = sub.json()["id"]

    for payload in (
        {"decision": "approved", "score": 11, "feedback": "x"},
        {"decision": "approved", "score": -1, "feedback": "x"},
        {"decision": "approved", "score": 8, "feedback": ""},
    ):
        r = client.post(
            f"/api/v1/submissions/{sub_id}/review", json=payload, headers=sup
        )
        assert r.status_code == 422, (payload, r.text)

    r = client.post(
        f"/api/v1/submissions/{sub_id}/review",
        json={"decision": "approved", "score": 8, "feedback": "solid"},
        headers=sup,
    )
    assert r.status_code == 200, r.text


# ---------------------------------------------------------------------------
# One active batch per intern + capacity
# ---------------------------------------------------------------------------


def test_one_active_batch_per_intern_and_capacity(client, admin):
    db = SessionLocal()
    try:
        batch = _create_batch_in_db("Workflow capacity batch", _sup_id(db), capacity=2)
    finally:
        db.close()

    me = client.get(
        "/api/v1/auth/me", headers=_login(client, "intern1@internflow.dev")
    ).json()

    # intern1 is already active in batch 1 -> second active batch must be rejected
    r = client.post(
        f"/api/v1/batches/{batch['id']}/interns",
        json={"user_id": me["id"]},
        headers=admin,
    )
    assert r.status_code == 400, r.text

    # capacity=2: first two fresh interns fit, third overflows
    interns = [
        _make_user_in_db(f"workflow-cap{i}@internflow.dev", "intern") for i in (1, 2, 3)
    ]
    for u in interns[:2]:
        r = client.post(
            f"/api/v1/batches/{batch['id']}/interns",
            json={"user_id": u["id"]},
            headers=admin,
        )
        assert r.status_code == 200, (u, r.text)

    r = client.post(
        f"/api/v1/batches/{batch['id']}/interns",
        json={"user_id": interns[2]["id"]},
        headers=admin,
    )
    assert r.status_code == 400, r.text


# ---------------------------------------------------------------------------
# Attendance: approved-leave exclusion + grace boundary + hours
# ---------------------------------------------------------------------------


def _attendance_intern_and_batch(client, admin) -> tuple[dict, dict]:
    """A fresh intern with an active membership in a fresh batch (no seed data)."""
    intern = _make_user_in_db("workflow-attendance@internflow.dev", "intern")
    db = SessionLocal()
    try:
        batch = _create_batch_in_db(
            "Workflow attendance batch", _sup_id(db), capacity=10
        )
    finally:
        db.close()

    r = client.post(
        f"/api/v1/batches/{batch['id']}/interns",
        json={"user_id": intern["id"]},
        headers=admin,
    )
    assert r.status_code == 200, r.text
    return intern, batch


def _next_weekdays(n: int) -> list[date]:
    days = []
    day = date.today()
    while len(days) < n:
        day += timedelta(days=1)
        if day.weekday() < 5:
            days.append(day)
    return days


def test_grace_period_boundary_via_service(client, admin, monkeypatch):
    import app.services.attendance as att_svc

    intern, batch = _attendance_intern_and_batch(client, admin)
    db = SessionLocal()
    try:
        intern_row = db.get(User, intern["id"])
        today = date.today()

        for offset_min, expect in ((0, "on_time"), (1, "late")):
            db.query(AttendanceRecord).filter(
                AttendanceRecord.intern_id == intern_row.id,
                AttendanceRecord.date == today,
            ).delete()
            now = datetime(today.year, today.month, today.day, 9, 20 + offset_min, 0, tzinfo=timezone.utc)
            monkeypatch.setattr(att_svc, "utcnow", (lambda n: lambda: n)(now))
            record = att_svc.check_in(db, intern_row)
            assert record is not None
            assert record.late_status.value == expect, (offset_min, expect)
            db.rollback()
    finally:
        db.close()


def test_approved_leave_excluded_from_absence(client, admin, monkeypatch):
    import app.services.attendance as att_svc

    intern, batch = _attendance_intern_and_batch(client, admin)
    db = SessionLocal()
    try:
        intern_row = db.get(User, intern["id"])
        days = _next_weekdays(2)

        # uncovered weekday absent
        absent_day, leave_day = days
        db.add(
            AttendanceRecord(
                intern_id=intern_row.id, batch_id=batch["id"], date=absent_day
            )
        )
        # leave-covered weekday: no check-in, but approved leave -> excluded
        db.add(
            AttendanceRecord(
                intern_id=intern_row.id, batch_id=batch["id"], date=leave_day
            )
        )
        db.add(
            LeaveRequest(
                intern_id=intern_row.id,
                batch_id=batch["id"],
                start_date=leave_day,
                end_date=leave_day,
                reason="approved leave",
                note="test",
                status="approved",
            )
        )
        db.commit()

        rows = att_svc.attendance_overview(db, batch["id"])
        row = next(r for r in rows if r["intern_id"] == intern_row.id)
        assert row.get("absent_days", 0) == 1, row
        assert row["absent_days"] == 1, row  # leave day not counted
        assert row["present_days"] == 0, row
        db.rollback()
    finally:
        db.close()


def test_attendance_hours_calculation(client, admin, monkeypatch):
    import app.services.attendance as att_svc

    intern, batch = _attendance_intern_and_batch(client, admin)
    db = SessionLocal()
    try:
        intern_row = db.get(User, intern["id"])
        today = date.today()
        db.add(
            AttendanceRecord(
                intern_id=intern_row.id,
                batch_id=batch["id"],
                date=today,
                check_in=datetime(today.year, today.month, today.day, 9, 0, tzinfo=timezone.utc),
            )
        )
        db.commit()

        out_at = datetime(today.year, today.month, today.day, 17, 30, tzinfo=timezone.utc)
        monkeypatch.setattr(att_svc, "utcnow", lambda: out_at)
        record = att_svc.check_out(db, intern_row)
        assert record is not None
        assert record.worked_hours == 8.5, record.worked_hours

        rows = att_svc.attendance_overview(db, batch["id"])
        row = next(r for r in rows if r["intern_id"] == intern_row.id)
        assert row["total_hours"] == 8.5, row
        assert row["present_days"] == 1, row
        db.rollback()
    finally:
        db.close()