"""Development seed script.

Creates demo accounts, an active batch, interns, tasks, submissions,
attendance records and company settings so the full demo scenario can run.

Usage:
    python -m app.db.seed            # create if missing (idempotent)
    python -m app.db.seed --force    # refuse to re-run when data exists
"""

import sys
from datetime import date, datetime, time, timedelta

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import (
    Announcement,
    AttendanceRecord,
    AttendanceRemark,
    Batch,
    BatchEvent,
    BatchMembership,
    CompanySettings,
    DeadlineExtension,
    Submission,
    SubmissionReview,
    Task,
    TaskAttachment,
    TaskCategory,
    TaskPriority,
    TaskScope,
    User,
    UserRole,
)
from app.models.enums import AttendanceStatus, ReviewDecision, SubmissionStatus

DEMO_PASSWORD = "Demo1234!"

ACCOUNTS = [
    ("admin@internflow.dev", "Alex Morgan", UserRole.ADMIN),
    ("supervisor@internflow.dev", "Dana Lee", UserRole.SUPERVISOR),
    ("intern1@internflow.dev", "Jordan Smith", UserRole.INTERN),
    ("intern2@internflow.dev", "Casey Johnson", UserRole.INTERN),
    ("intern3@internflow.dev", "Riley Patel", UserRole.INTERN),
    ("intern4@internflow.dev", "Taylor Nguyen", UserRole.INTERN),
]


def seed(force: bool = False) -> int:
    db = SessionLocal()
    created = 0
    try:
        if db.query(User).count() > 0:
            print("Seed data already present; skipping (use --force to bypass guard).")
            return 0

        # --- company settings ---
        company = CompanySettings(
            id=1,
            company_name="InternFlow HQ",
            description="Software company running the internship program",
            default_start_time="09:00",
            default_end_time="18:00",
            default_grace_minutes=20,
        )
        db.add(company)
        created += 1

        # --- accounts ---
        users: dict[str, User] = {}
        for email, full_name, role in ACCOUNTS:
            user = User(
                email=email,
                full_name=full_name,
                role=role,
                password_hash=hash_password(DEMO_PASSWORD),
                must_reset_password=False,
                is_active=True,
            )
            db.add(user)
            db.flush()
            users[email] = user
            created += 1

        supervisor = users["supervisor@internflow.dev"]
        interns = [
            users["intern1@internflow.dev"],
            users["intern2@internflow.dev"],
            users["intern3@internflow.dev"],
            users["intern4@internflow.dev"],
        ]

        # --- batch ---
        today = date.today()
        batch = Batch(
            name="Summer 2026 Backend Engineering",
            description="Internship batch focused on backend engineering fundamentals",
            start_date=today - timedelta(days=21),
            end_date=today + timedelta(days=14),
            supervisor_id=supervisor.id,
            capacity=8,
            start_time="09:00",
            end_time="18:00",
            grace_minutes=20,
            status="active",
        )
        db.add(batch)
        db.flush()
        created += 1

        for intern in interns:
            db.add(BatchMembership(batch_id=batch.id, intern_id=intern.id, is_active=True))
            created += 1

        # --- tasks ---
        t1 = Task(
            title="Set up REST API with FastAPI",
            description="Build a CRUD API with FastAPI and PostgreSQL. Include auth, schemas and tests.",
            scope=TaskScope.BATCH,
            batch_id=batch.id,
            created_by=supervisor.id,
            category=TaskCategory.DEVELOPMENT,
            priority=TaskPriority.HIGH,
            deadline=datetime.combine(today + timedelta(days=7), time(17, 0)),
            estimated_effort_hours=16,
            status="open",
        )
        t2 = Task(
            title="Write internship documentation",
            description="Summarize the onboarding process and environment setup.",
            scope=TaskScope.BATCH,
            batch_id=batch.id,
            created_by=supervisor.id,
            category=TaskCategory.DOCUMENTATION,
            priority=TaskPriority.MEDIUM,
            deadline=datetime.combine(today + timedelta(days=3), time(17, 0)),
            estimated_effort_hours=4,
            status="open",
        )
        t3 = Task(
            title="Design the weekly review slide deck",
            description="Create a 5-slide deck covering progress so far.",
            scope=TaskScope.INDIVIDUAL,
            batch_id=batch.id,
            assignee_id=interns[2].id,
            created_by=supervisor.id,
            category=TaskCategory.PRESENTATION,
            priority=TaskPriority.LOW,
            deadline=datetime.combine(today + timedelta(days=10), time(17, 0)),
            estimated_effort_hours=6,
            status="open",
        )
        t4 = Task(
            title="Sample index endpoint",
            description="Add a /health-style sample endpoint with an integration test.",
            scope=TaskScope.BATCH,
            batch_id=batch.id,
            created_by=supervisor.id,
            category=TaskCategory.TESTING,
            priority=TaskPriority.MEDIUM,
            deadline=datetime.combine(today - timedelta(days=2), time(17, 0)),
            estimated_effort_hours=2,
            status="submitted",
        )
        db.add_all([t1, t2, t3, t4])
        db.flush()
        for _ in range(4):
            created += 1

        db.add(
            TaskAttachment(
                task_id=t1.id,
                filename="reference_starter.zip",
                storage_key="task_attachments/demo-starter.zip",
                content_type="application/zip",
                size_bytes=2048,
            )
        )
        created += 1

        # --- submissions + reviews ---
        sub = Submission(
            task_id=t4.id,
            intern_id=interns[0].id,
            batch_id=batch.id,
            version=1,
            github_url="https://github.com/jordan-sample/internflow-task4",
            live_url="https://demo.internflow.dev",
            notes="Implemented the sample endpoint and added a passing integration test.",
            actual_effort_hours=2.5,
            submitted_at=datetime.utcnow() - timedelta(hours=26),
            is_late=True,
            late_reason="Machine setup took longer than expected.",
            status=SubmissionStatus.APPROVED,
        )
        db.add(sub)
        db.flush()
        db.add(
            SubmissionReview(
                submission_id=sub.id,
                supervisor_id=supervisor.id,
                decision=ReviewDecision.APPROVED,
                score=8.5,
                feedback="Clean implementation and a solid test. Good structure.",
            )
        )
        created += 2

        sub2 = Submission(
            task_id=t2.id,
            intern_id=interns[1].id,
            batch_id=batch.id,
            version=1,
            github_url="https://github.com/casey-sample/docs",
            notes="Initial draft.",
            actual_effort_hours=3,
            submitted_at=datetime.utcnow() - timedelta(hours=5),
            is_late=False,
            status=SubmissionStatus.CHANGES_REQUESTED,
        )
        db.add(sub2)
        db.flush()
        db.add(
            SubmissionReview(
                submission_id=sub2.id,
                supervisor_id=supervisor.id,
                decision=ReviewDecision.CHANGES_REQUESTED,
                score=6.0,
                feedback="Good start — add a troubleshooting section and screenshots.",
            )
        )
        created += 2

        # --- attendance (last ~10 working days) ---
        for day_offset in range(1, 11):
            day = today - timedelta(days=day_offset)
            if day.weekday() >= 5:
                continue
            for intern in interns:
                check_in = datetime.combine(day, time(9, 0)) + timedelta(minutes=(intern.id % 3) * 10)
                check_out = check_in + timedelta(hours=8, minutes=(intern.id % 4) * 25)
                late = AttendanceStatus.LATE if check_in.hour == 9 and check_in.minute > 20 else AttendanceStatus.ON_TIME
                record = AttendanceRecord(
                    intern_id=intern.id,
                    batch_id=batch.id,
                    date=day,
                    check_in=check_in,
                    check_out=check_out,
                    late_status=late,
                    worked_hours=round((check_out - check_in).total_seconds() / 3600, 2),
                    work_done=f"Worked on backend tasks for batch {batch.name}",
                    blockers="",
                    next_day_plan="Continue task work",
                )
                db.add(record)
                created += 1

        first_intern_record = (
            db.query(AttendanceRecord).filter(AttendanceRecord.intern_id == interns[0].id).first()
        )
        if first_intern_record:
            db.add(
                AttendanceRemark(
                    attendance_id=first_intern_record.id,
                    supervisor_id=supervisor.id,
                    remark="Consistently on time and making solid progress.",
                )
            )
            created += 1

        # --- announcement + event ---
        db.add(
            Announcement(
                batch_id=batch.id,
                author_id=supervisor.id,
                title="Weekly review session Friday",
                content="We'll run the weekly review at 14:00 on Friday. Be prepared to demo progress.",
                is_pinned=True,
            )
        )
        created += 1
        db.add(
            BatchEvent(
                batch_id=batch.id,
                title="Final presentation",
                event_type="presentation",
                starts_at=datetime.combine(today + timedelta(days=14), time(14, 0)),
                ends_at=datetime.combine(today + timedelta(days=14), time(16, 0)),
                location="Conference Room B",
                details="Each intern presents their final project.",
                created_by=supervisor.id,
            )
        )
        created += 1

        # --- deadline extension example ---
        db.add(
            DeadlineExtension(
                task_id=t1.id,
                intern_id=interns[3].id,
                original_deadline=t1.deadline,
                new_deadline=t1.deadline + timedelta(days=2),
                reason="Personal scheduling conflict",
                granted_by=supervisor.id,
            )
        )
        created += 1

        db.commit()
        print(f"Seed complete — {created} records created.")
        print("Demo accounts (password: Demo1234!):")
        for email, name, _ in ACCOUNTS:
            print(f"  {name:<18} {email:<32} {name.split()[-1].lower()}")
        return created
    finally:
        db.close()


if __name__ == "__main__":
    force = "--force" in sys.argv
    seed(force=force)