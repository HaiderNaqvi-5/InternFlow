"""Smoke test for core InternFlow workflows (P0/P1) against a running server
or via TestClient. Run: .venv/bin/python scripts/smoke_test.py"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from fastapi.testclient import TestClient

    from app.main import app
except ImportError as exc:
    print(f"ImportError: {exc}")
    TestClient = None

PASSWORD = "Demo1234!"
FAILURES = []


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))
    if not condition:
        FAILURES.append(name)


def reset_db():
    """Empty all tables and reseed so the run is deterministic."""
    from sqlalchemy import inspect, text

    from app.db.base import Base
    from app.db.session import engine

    insp = inspect(engine)
    with engine.begin() as conn:
        for table in reversed(insp.get_table_names()):
            conn.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))
    Base.metadata.create_all(engine)
    from app.db.seed import seed

    seed()


def main():
    if TestClient is None:
        print("TestClient unavailable")
        sys.exit(2)
    reset_db()
    client = TestClient(app)

    def login(email):
        r = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
        assert r.status_code == 200, (email, r.text)
        return r.json()["access_token"]

    def auth(token):
        return {"Authorization": f"Bearer {token}"}

    # --- Auth ---
    print("AUTH")
    admin_tok = login("admin@internflow.dev")
    sup_tok = login("supervisor@internflow.dev")
    int1_tok = login("intern1@internflow.dev")
    int2_tok = login("intern2@internflow.dev")
    me = client.get("/api/v1/auth/me", headers=auth(admin_tok)).json()
    check("admin /auth/me", me["role"] == "admin", me["email"])
    bad = client.post("/api/v1/auth/login", json={"email": "admin@internflow.dev", "password": "wrong"})
    check("bad login rejected", bad.status_code == 401)

    # --- Users / RBAC ---
    print("USERS / RBAC")
    users = client.get("/api/v1/users?page_size=50", headers=auth(admin_tok)).json()
    check("admin lists users", users["total"] >= 6)
    intern_list = client.get("/api/v1/users?page_size=50", headers=auth(int1_tok))
    check(
        "intern sees only self in user list",
        intern_list.status_code == 200 and intern_list.json()["total"] == 1,
        str(intern_list.json()["total"]),
    )
    create_role_denied = client.post(
        "/api/v1/users",
        headers=auth(sup_tok),
        json={"email": "x@example.com", "full_name": "X", "role": "intern"},
    )
    check("supervisor cannot create users", create_role_denied.status_code == 403)

    # --- Batches ---
    print("BATCHES")
    batches = client.get("/api/v1/batches?page_size=50", headers=auth(admin_tok)).json()
    check("admin lists batches", batches["total"] >= 1)
    batch = batches["items"][0]
    bid = batch["id"]
    check("batch has capacity/intern count", batch.get("active_intern_count") == 4)
    sb = client.get(f"/api/v1/batches/{bid}", headers=auth(sup_tok))
    check("supervisor reads assigned batch", sb.status_code == 200)
    other_intern = client.get(f"/api/v1/batches/{bid}", headers=auth(int1_tok))
    check("intern reads own batch", other_intern.status_code == 200)

    # capacity rule
    new_intern = client.post(
        "/api/v1/users",
        headers=auth(admin_tok),
        json={"email": "overflow.intern@example.com", "full_name": "Overflow Intern", "role": "intern"},
    ).json()
    add_over = client.post(
        f"/api/v1/batches/{bid}/interns",
        headers=auth(admin_tok),
        json={"user_id": new_intern["id"]},
    )
    # capacity is 8; only 4 seated, so should succeed
    check("add intern within capacity", add_over.status_code == 200, add_over.text[:80])

    # --- Tasks (supervisor) ---
    print("TASKS")
    t_new = client.post(
        "/api/v1/tasks",
        headers=auth(sup_tok),
        json={
            "title": "Smoke Task A",
            "description": "Test task",
            "scope": "batch",
            "batch_id": bid,
            "category": "Development",
            "priority": "High",
            "deadline": (datetime.utcnow() + timedelta(days=3)).isoformat(),
            "estimated_effort_hours": 8,
        },
    )
    check("supervisor creates batch task", t_new.status_code == 200, t_new.text[:120])
    t1 = t_new.json()

    # intern can see it
    tasks_intern = client.get("/api/v1/tasks?page_size=50", headers=auth(int1_tok)).json()
    check("intern sees batch task", any(x["id"] == t1["id"] for x in tasks_intern["items"]))

    # --- Submission + late + review ---
    print("SUBMISSIONS / REVIEWS")
    sub = client.post(
        f"/api/v1/submissions/{t1['id']}",
        headers=auth(int1_tok),
        json={"github_url": "https://github.com/demo", "notes": "done", "actual_effort_hours": 3},
    )
    check("intern submits work", sub.status_code == 200, sub.text[:150])
    sid = sub.json()["id"]

    rev = client.post(
        f"/api/v1/submissions/{sid}/review",
        headers=auth(sup_tok),
        json={"decision": "changes_requested", "score": 7, "feedback": "Please improve"},
    )
    check("supervisor reviews with score+feedback", rev.status_code == 200, rev.text[:120])

    # resubmit
    sub2 = client.post(
        f"/api/v1/submissions/{t1['id']}",
        headers=auth(int1_tok),
        json={"github_url": "https://github.com/demo-v2", "notes": "revised"},
    )
    check("intern resubmits after changes", sub2.status_code == 200, sub2.text[:120])
    check("resubmission is version 2", sub2.json()["version"] == 2)

    # mandatory score validation
    rev_bad = client.post(
        f"/api/v1/submissions/{sub2.json()['id']}/review",
        headers=auth(sup_tok),
        json={"decision": "approved", "score": 11, "feedback": "x"},
    )
    check("score >10 rejected", rev_bad.status_code == 422)

    # --- Attendance ---
    print("ATTENDANCE")
    cin = client.post("/api/v1/attendance/check-in", headers=auth(int1_tok))
    check("intern check-in", cin.status_code == 200, cin.text[:100])
    clog = client.post(
        "/api/v1/attendance/daily-log",
        headers=auth(int1_tok),
        json={"work_done": "Built the API", "blockers": "none", "next_day_plan": "Continue"},
    )
    check("daily log saved", clog.status_code == 200)
    summary = client.get("/api/v1/attendance/summary", headers=auth(sup_tok)).json()
    check("supervisor attendance summary", isinstance(summary, list) and len(summary) >= 4)

    # --- Comments / mentions ---
    print("COMMENTS")
    intern2_id = [
        u for u in client.get("/api/v1/users?page_size=50", headers=auth(admin_tok)).json()["items"]
        if u["email"] == "intern2@internflow.dev"
    ][0]["id"]
    comment = client.post(
        f"/api/v1/tasks/{t1['id']}/comments",
        headers=auth(int1_tok),
        json={"content": "Hey @Casey check this out", "mentions": [intern2_id]},
    )
    check("intern comments with mention", comment.status_code == 200, comment.text[:100])
    pins = client.post(
        f"/api/v1/comments/{comment.json()['id']}/pin?pin=true",
        headers=auth(sup_tok),
    )
    check("supervisor pins comment", pins.status_code == 200)
    dele = client.delete(f"/api/v1/comments/{comment.json()['id']}", headers=auth(int1_tok))
    check("author deletes comment", dele.status_code == 200)

    # --- Notifications (mention) ---
    print("NOTIFICATIONS")
    notifs = client.get("/api/v1/notifications?limit=20", headers=auth(int2_tok)).json()
    check("mention generates notification", notifs["total"] >= 1, str(notifs["total"]))

    # --- Analytics ---
    print("ANALYTICS")
    ia = client.get("/api/v1/analytics/intern", headers=auth(int1_tok)).json()
    check("intern analytics present", "average_score" in ia)
    sa = client.get("/api/v1/analytics/supervisor", headers=auth(sup_tok)).json()
    check("supervisor analytics present", "tasks_total" in sa)
    ha = client.get("/api/v1/analytics/hr", headers=auth(admin_tok)).json()
    check("hr analytics present", "active_batches" in ha)

    # --- Search ---
    print("SEARCH")
    sr = client.get("/api/v1/search?q=Smoke", headers=auth(sup_tok)).json()
    check("search finds task", any(r["label"] == "Smoke Task A" for r in sr["results"]))

    # --- Extensions ---
    print("EXTENSIONS")
    ext = client.post(
        f"/api/v1/tasks/{t1['id']}/extensions",
        headers=auth(sup_tok),
        json={
            "task_id": t1["id"],
            "intern_id": intern2_id,
            "new_deadline": (datetime.utcnow() + timedelta(days=5)).isoformat(),
            "reason": "Smoke test extension",
        },
    )
    check("supervisor grants extension", ext.status_code == 200, ext.text[:120])

    # --- Report + Certificate ---
    print("REPORTS / CERTIFICATES")
    report = client.post(
        f"/api/v1/reports/internship-report/{new_intern['id']}/{bid}",
        headers=auth(admin_tok),
    )
    check("HR generates internship report", report.status_code == 200, report.text[:120])
    completion = client.post(
        f"/api/v1/completions?intern_id={new_intern['id']}&batch_id={bid}",
        headers=auth(admin_tok),
    )
    check("HR completes internship -> certificate", completion.status_code == 200, completion.text[:200])
    certs = client.get("/api/v1/certificates", headers=auth(admin_tok)).json()
    check("certificate listed", len(certs) >= 1)
    if certs:
        dl = client.get(f"/api/v1/certificates/{certs[0]['id']}/download", headers=auth(admin_tok))
        check("certificate downloads as PDF", dl.status_code == 200 and dl.content[:4] == b"%PDF")

    # --- Audit ---
    print("AUDIT")
    audit = client.get("/api/v1/audit?page_size=10", headers=auth(admin_tok)).json()
    check("audit log has entries", audit["total"] > 5, str(audit["total"]))

    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} checks")
        for f in FAILURES:
            print(f"  - {f}")
        sys.exit(1)
    print("ALL SMOKE CHECKS PASSED")


if __name__ == "__main__":
    main()