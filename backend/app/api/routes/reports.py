import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.permissions import require_admin
from app.db.session import get_db
from app.models import (
    Batch,
    Report,
    Submission,
    Task,
    User,
    UserRole,
)
from app.services.docs import generate_internship_report
from app.utils.storage import storage

router = APIRouter(tags=["reports"])

EXPORT_PREFIX = "/reports/exports"
REPORTS_PREFIX = "/reports"


def _rows_for_attendance(db: Session, batch_id: int | None) -> list[dict]:
    from app.services.attendance import attendance_overview

    if batch_id:
        return attendance_overview(db, batch_id)
    batches = db.execute(select(Batch).where(Batch.status == "active")).scalars().all()
    rows: list[dict] = []
    for b in batches:
        rows.extend(attendance_overview(db, b.id))
    return rows


@router.get(EXPORT_PREFIX + "/attendance")
def export_attendance(
    format: str = "csv",
    batch_id: int | None = None,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    rows = _rows_for_attendance(db, batch_id)
    if format == "xlsx":
        content, media = _attendance_xlsx(rows)
    else:
        content, media = _attendance_csv(rows)
    record_audit(db, admin, "exports.attendance", metadata={"format": format, "batch_id": batch_id})
    return Response(content, media_type=media, headers={"Content-Disposition": 'attachment; filename="attendance-export.csv"' if format != "xlsx" else 'attachment; filename="attendance-export.xlsx"'})


def _attendance_csv(rows: list[dict]) -> tuple[bytes, str]:
    import csv

    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=["intern_id", "intern_name", "workdays", "present_days", "late_days", "absent_days", "total_hours", "attendance_rate"],
    )
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    return buf.getvalue().encode("utf-8"), "text/csv"


def _attendance_xlsx(rows: list[dict]) -> tuple[bytes, str]:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Attendance"
    headers = ["Intern ID", "Name", "Workdays", "Present", "Late", "Absent", "Total Hours", "Attendance %"]
    ws.append(headers)
    for r in rows:
        ws.append([r.get("intern_id"), r.get("intern_name"), r.get("workdays"), r.get("present_days"), r.get("late_days"), r.get("absent_days", 0), r.get("total_hours"), r.get("attendance_rate")])
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get(EXPORT_PREFIX + "/evaluations")
def export_evaluations(
    format: str = "csv",
    batch_id: int | None = None,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = select(Submission).order_by(Submission.submitted_at.desc())
    if batch_id:
        query = query.where(Submission.batch_id == batch_id)
    subs = db.execute(query).scalars().all()

    header = ["Task", "Intern", "Version", "Status", "Score", "Decision", "Feedback", "Submitted"]
    rows = []
    for s in subs:
        task = db.get(Task, s.task_id)
        intern = db.get(User, s.intern_id)
        for r in sorted(s.reviews, key=lambda r: r.reviewed_at):
            rows.append(
                [
                    task.title if task else s.task_id,
                    intern.full_name if intern else s.intern_id,
                    s.version,
                    s.status.value,
                    r.score,
                    r.decision.value,
                    r.feedback,
                    s.submitted_at.isoformat(),
                ]
            )

    if format == "xlsx":
        import openpyxl

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Evaluations"
        ws.append(header)
        for row in rows:
            ws.append(row)
        out = io.BytesIO()
        wb.save(out)
        record_audit(db, admin, "exports.evaluations", metadata={"format": format, "batch_id": batch_id})
        return Response(out.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": 'attachment; filename="evaluations.xlsx"'})

    import csv

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    writer.writerows(rows)
    record_audit(db, admin, "exports.evaluations", metadata={"format": format, "batch_id": batch_id})
    return Response(buf.getvalue().encode("utf-8"), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="evaluations.csv"'})


@router.post(REPORTS_PREFIX + "/internship-report/{intern_id}/{batch_id}")
def generate_report(
    intern_id: int,
    batch_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    intern = db.get(User, intern_id)
    batch = db.get(Batch, batch_id)
    if intern is None or intern.role != UserRole.INTERN:
        raise HTTPException(status_code=404, detail="Intern not found")
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    content, filename = generate_internship_report(db, intern, batch, admin)
    key = storage.new_key("reports", filename)
    storage.save_bytes(key, content)
    report = Report(
        intern_id=intern_id,
        batch_id=batch_id,
        report_type="internship_report",
        file_key=key,
        filename=filename,
        generated_by=admin.id,
    )
    db.add(report)
    db.flush()
    record_audit(db, admin, "reports.generate", "report", report.id, {"intern_id": intern_id, "batch_id": batch_id})
    db.commit()
    db.refresh(report)
    return {"report_id": report.id, "filename": filename, "generated_at": report.generated_at.isoformat()}


@router.get(REPORTS_PREFIX + "/{report_id}/download")
def download_report(
    report_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    content = storage.read_bytes(report.file_key)
    return Response(
        content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{report.filename}"'},
    )


@router.get(REPORTS_PREFIX)
def list_reports(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        select(Report).order_by(Report.generated_at.desc()).limit(100)
    ).scalars().all()
    return [
        {
            "id": r.id,
            "intern_id": r.intern_id,
            "batch_id": r.batch_id,
            "filename": r.filename,
            "generated_at": r.generated_at.isoformat(),
        }
        for r in rows
    ]