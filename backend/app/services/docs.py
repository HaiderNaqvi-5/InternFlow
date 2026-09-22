import io
import os
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Batch,
    CompanySettings,
    InternshipOutcome,
    Submission,
    User,
)
from app.models.enums import SubmissionStatus

_FONT_CANDIDATES = [
    "/usr/share/fonts/noto/NotoSans-Regular.ttf",
    "/usr/share/fonts/noto/NotoSans-Bold.ttf",
]

_REGISTERED = False


def _register_fonts() -> None:
    global _REGISTERED
    if _REGISTERED:
        return
    normal = next((p for p in _FONT_CANDIDATES if os.path.exists(p)), None)
    if not normal:
        return
    pdfmetrics.registerFont(TTFont("DejaVu", normal))
    bold = _FONT_CANDIDATES[1] if os.path.exists(_FONT_CANDIDATES[1]) else normal
    pdfmetrics.registerFont(TTFont("DejaVu-Bold", bold))
    _REGISTERED = True


def _styles():
    _register_fonts()
    styles = getSampleStyleSheet()
    return {
        "h1": ParagraphStyle("h1", parent=styles["h1"], fontName="DejaVu-Bold"),
        "sub": ParagraphStyle("sub", parent=styles["Normal"], fontName="DejaVu", spaceAfter=12, textColor=colors.HexColor("#64748b")),
        "body": ParagraphStyle("body", parent=styles["Normal"], fontName="DejaVu", fontSize=10, leading=15),
        "small": ParagraphStyle("small", parent=styles["Normal"], fontName="DejaVu", fontSize=9, leading=13, textColor=colors.HexColor("#475569")),
    }


def _company_report_styles() -> dict:
    return _styles()


def _build_internship_summary(db: Session, intern: User, batch: Batch) -> dict:
    submissions = db.execute(
        select(Submission).where(
            Submission.intern_id == intern.id, Submission.batch_id == batch.id
        )
    ).scalars()
    tasks_done = 0
    approved = 0
    late = 0
    scores: list[float] = []
    for sub in submissions:
        if sub.status in (SubmissionStatus.APPROVED, SubmissionStatus.CHANGES_REQUESTED, SubmissionStatus.REJECTED):
            tasks_done += 1
        if sub.is_late:
            late += 1
        for review in sub.reviews:
            scores.append(review.score)
        if sub.status == SubmissionStatus.APPROVED:
            approved += 1
    avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0

    from app.services.attendance import attendance_overview

    att = attendance_overview(db, batch.id)
    intern_att = next((a for a in att if a["intern_id"] == intern.id), None)

    outcome = db.execute(
        select(InternshipOutcome).where(
            InternshipOutcome.intern_id == intern.id, InternshipOutcome.batch_id == batch.id
        )
    ).scalar_one_or_none()

    return {
        "intern": intern,
        "batch": batch,
        "total_tasks_done": tasks_done,
        "approved_tasks": approved,
        "late_submissions": late,
        "average_score": avg_score,
        "attendance": intern_att or {"present_days": 0, "late_days": 0, "total_hours": 0.0, "attendance_rate": 0.0},
        "outcome": outcome,
    }


def generate_internship_report(db: Session, intern: User, batch: Batch, generated_by: User) -> tuple[bytes, str]:
    styles = _styles()
    summary = _build_internship_summary(db, intern, batch)
    att = summary["attendance"]
    outcome = summary["outcome"]

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        rightMargin=18 * mm, leftMargin=18 * mm, topMargin=18 * mm, bottomMargin=18 * mm,
    )
    story: list = []
    story.append(Paragraph("Internship Final Report", styles["h1"]))
    story.append(Paragraph(f"{intern.full_name} &mdash; {batch.name}", styles["sub"]))
    story.append(Spacer(1, 4 * mm))

    data = [
        ["Intern", intern.full_name],
        ["Email", intern.email],
        ["Batch", batch.name],
        ["Duration", f"{batch.start_date} to {batch.end_date}"],
        ["Attendance rate", f'{att.get("attendance_rate", 0)}%'],
        ["Present days", str(att.get("present_days", 0))],
        ["Late check-ins", str(att.get("late_days", 0))],
        ["Total hours logged", str(att.get("total_hours", 0.0))],
        ["Tasks completed", str(summary["total_tasks_done"])],
        ["Tasks approved", str(summary["approved_tasks"])],
        ["Late submissions", str(summary["late_submissions"])],
        ["Average evaluation score", f'{summary["average_score"]}/10'],
    ]
    table = Table(data, colWidths=[50 * mm, 115 * mm])
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "DejaVu"),
                ("FONTNAME", (0, 0), (0, -1), "DejaVu-Bold"),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 6 * mm))

    recommendation = outcome.supervisor_recommendation if outcome and outcome.supervisor_recommendation else "Not provided"
    completion = outcome.hr_completion_status if outcome else "not_completed"
    story.append(Paragraph(f"Supervisor final recommendation: <b>{recommendation.replace('_', ' ').title()}</b>", styles["body"]))
    story.append(Paragraph(f"HR completion status: <b>{completion.replace('_', ' ').title()}</b>", styles["body"]))
    story.append(Paragraph(
        "This report is auto-generated by InternFlow and summarizes attendance, task "
        "completion, evaluations and overall performance for the internship period.",
        styles["small"],
    ))
    doc.build(story)
    filename = f"internship-report-{intern.id}-{batch.id}-{date.today().isoformat()}.pdf"
    return buf.getvalue(), filename


def generate_certificate(
    db: Session,
    intern: User,
    batch: Batch,
    settings_row: CompanySettings,
    ceo_key: str | None,
    instructor_key: str | None,
) -> tuple[bytes, str]:
    styles = _styles()
    buf = io.BytesIO()
    page = landscape(A4)
    doc = SimpleDocTemplate(buf, pagesize=page, rightMargin=22 * mm, leftMargin=22 * mm, topMargin=22 * mm, bottomMargin=22 * mm)
    story: list = []

    company = settings_row.company_name or "InternFlow"
    story.append(Paragraph(company, ParagraphStyle("cmp", parent=styles["h1"], fontSize=26, alignment=1, textColor=colors.HexColor("#0f172a"))))
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("Certificate of Completion", ParagraphStyle("ttl", parent=styles["h1"], fontSize=34, alignment=1, spaceAfter=10)))
    story.append(Paragraph(
        "This certificate is proudly presented to",
        ParagraphStyle("lbl", parent=styles["body"], alignment=1, spaceAfter=14),
    ))
    story.append(Paragraph(
        intern.full_name,
        ParagraphStyle("name", parent=styles["h1"], fontSize=30, alignment=1, textColor=colors.HexColor("#2563eb")),
    ))
    story.append(Paragraph(
        f"for successfully completing the internship program <b>{batch.name}</b> "
        f"from {batch.start_date} to {batch.end_date}.",
        ParagraphStyle("body2", parent=styles["body"], alignment=1, spaceBefore=14),
    ))
    story.append(Spacer(1, 14 * mm))

    sig_flow: list = []
    if instructor_key:
        sig_flow.append(Image(_resolve_asset(instructor_key), width=34 * mm, height=16 * mm))
    if ceo_key:
        sig_flow.append(Image(_resolve_asset(ceo_key), width=34 * mm, height=16 * mm))

    label = "Instructor / Supervisor" if instructor_key else "Supervisor"
    signatory = batch.supervisor.full_name if batch.supervisor else "Supervisor"
    sig_flow.append(Paragraph(f"<b>{signatory}</b><br/>{label}", ParagraphStyle("sig", parent=styles["small"], alignment=1, spaceBefore=6)))
    if ceo_key and instructor_key:
        sig_flow.append(Paragraph("<b>CEO</b>", ParagraphStyle("ceo", parent=styles["small"], alignment=1, spaceBefore=6)))

    sig_table = Table([sig_flow], colWidths=[60 * mm, 60 * mm, 50 * mm])
    sig_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.append(sig_table)
    doc.build(story)
    filename = f"certificate-{intern.id}-{batch.id}.pdf"
    return buf.getvalue(), filename


def _resolve_asset(key: str) -> str:
    from app.utils.storage import storage

    return str(storage._resolve(key))