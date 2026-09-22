from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.permissions import get_current_user, require_admin
from app.db.session import get_db
from app.models import (
    Batch,
    Certificate,
    CompanySettings,
    InternshipOutcome,
    User,
    UserRole,
)
from app.services.access import ensure_supervisor_manages
from app.services.docs import generate_certificate
from app.services.notifications import notify_many
from app.utils.storage import storage

router = APIRouter(tags=["certificates"])

COMPLETION_PREFIX = "/completions"
CERT_PREFIX = "/certificates"


@router.post(COMPLETION_PREFIX)
def complete_internship(
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

    outcome = db.execute(
        select(InternshipOutcome).where(
            InternshipOutcome.intern_id == intern_id,
            InternshipOutcome.batch_id == batch_id,
        )
    ).scalar_one_or_none()
    if outcome is None:
        outcome = InternshipOutcome(intern_id=intern_id, batch_id=batch_id)
        db.add(outcome)
    outcome.hr_completion_status = "successfully_completed"
    outcome.completed_on = date.today()
    db.flush()

    settings_row = db.get(CompanySettings, 1) or CompanySettings(id=1, company_name="InternFlow")
    if settings_row.id != 1:
        db.add(settings_row)
        db.flush()

    cert = db.execute(
        select(Certificate).where(
            Certificate.intern_id == intern_id, Certificate.batch_id == batch_id
        )
    ).scalar_one_or_none()
    if cert is None:
        content, filename = generate_certificate(
            db,
            intern,
            batch,
            settings_row,
            settings_row.signature_ceo_key,
            settings_row.signature_instructor_key,
        )
        key = storage.new_key("certificates", filename)
        storage.save_bytes(key, content)
        cert = Certificate(
            intern_id=intern_id,
            batch_id=batch_id,
            template_version="v1",
            signature_ceo_key=settings_row.signature_ceo_key,
            signature_instructor_key=settings_row.signature_instructor_key,
            file_key=key,
            filename=filename,
        )
        db.add(cert)

    notify_many(
        db, [intern_id], "internship_completed",
        "Internship Successfully Completed",
        f"Congratulations {intern.full_name}! Your certificate has been issued.",
        link="/certificates",
        actor_id=admin.id,
    )
    record_audit(
        db, admin, "completion.mark_success", "internship", intern_id,
        {"batch_id": batch_id},
    )
    db.commit()
    return {
        "message": "Internship marked Successfully Completed and certificate generated",
        "certificate_id": cert.id if cert else None,
        "outcome": outcome.hr_completion_status,
    }


@router.post(COMPLETION_PREFIX + "/recommendation")
def supervisor_recommendation(
    intern_id: int,
    batch_id: int,
    recommendation: str,
    caller: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if caller.role not in (UserRole.SUPERVISOR, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Only supervisors can set recommendations")
    if caller.role == UserRole.SUPERVISOR:
        ensure_supervisor_manages(db, caller, batch_id)

    if recommendation not in ("successfully_completed", "completed_with_concerns", "needs_extension"):
        raise HTTPException(status_code=400, detail="Invalid recommendation")
    outcome = db.execute(
        select(InternshipOutcome).where(
            InternshipOutcome.intern_id == intern_id,
            InternshipOutcome.batch_id == batch_id,
        )
    ).scalar_one_or_none()
    if outcome is None:
        outcome = InternshipOutcome(intern_id=intern_id, batch_id=batch_id)
        db.add(outcome)
    outcome.supervisor_recommendation = recommendation
    record_audit(
        db, caller, "completion.recommendation", "internship", intern_id,
        {"batch_id": batch_id, "recommendation": recommendation},
    )
    db.commit()
    return {"message": "Recommendation saved", "recommendation": recommendation}


@router.get(COMPLETION_PREFIX)
def list_outcomes(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = select(InternshipOutcome)
    if user.role == UserRole.INTERN:
        query = query.where(InternshipOutcome.intern_id == user.id)
    elif user.role == UserRole.SUPERVISOR:
        query = query.where(
            InternshipOutcome.batch_id.in_(
                select(Batch.id).where(Batch.supervisor_id == user.id)
            )
        )
    rows = db.execute(query.order_by(InternshipOutcome.updated_at.desc()).limit(200)).scalars().all()
    result = []
    for o in rows:
        intern = db.get(User, o.intern_id)
        batch = db.get(Batch, o.batch_id)
        result.append(
            {
                "intern_id": o.intern_id,
                "intern_name": intern.full_name if intern else None,
                "batch_id": o.batch_id,
                "batch_name": batch.name if batch else None,
                "supervisor_recommendation": o.supervisor_recommendation,
                "hr_completion_status": o.hr_completion_status,
                "completed_on": o.completed_on.isoformat() if o.completed_on else None,
            }
        )
    return result


@router.get(CERT_PREFIX)
def my_certificates(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = select(Certificate)
    if user.role == UserRole.INTERN:
        query = query.where(Certificate.intern_id == user.id)
    elif user.role == UserRole.SUPERVISOR:
        query = query.where(
            Certificate.batch_id.in_(
                select(Batch.id).where(Batch.supervisor_id == user.id)
            )
        )
    rows = db.execute(query.order_by(Certificate.issued_at.desc()).limit(100)).scalars().all()
    result = []
    for c in rows:
        intern = db.get(User, c.intern_id)
        batch = db.get(Batch, c.batch_id)
        result.append(
            {
                "id": c.id,
                "intern_id": c.intern_id,
                "intern_name": intern.full_name if intern else None,
                "batch_id": c.batch_id,
                "batch_name": batch.name if batch else None,
                "filename": c.filename,
                "issued_at": c.issued_at.isoformat(),
            }
        )
    return result


@router.get(CERT_PREFIX + "/{certificate_id}/download")
def download_certificate(
    certificate_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cert = db.get(Certificate, certificate_id)
    if cert is None:
        raise HTTPException(status_code=404, detail="Certificate not found")
    if user.role == UserRole.INTERN and cert.intern_id != user.id:
        raise HTTPException(status_code=403, detail="Not your certificate")
    if user.role == UserRole.SUPERVISOR:
        batch = db.get(Batch, cert.batch_id)
        if batch is None or batch.supervisor_id != user.id:
            raise HTTPException(status_code=403, detail="Not the assigned supervisor")
    if not cert.file_key:
        raise HTTPException(status_code=404, detail="Certificate not generated")
    content = storage.read_bytes(cert.file_key)
    return Response(
        content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{cert.filename or "certificate.pdf"}"'},
    )