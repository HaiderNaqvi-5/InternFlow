from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.permissions import require_admin
from app.db.session import get_db
from app.models import CompanySettings, User
from app.schemas.batch import CompanySettingsOut, CompanySettingsUpdate
from app.utils.storage import read_upload, storage

router = APIRouter(prefix="/company", tags=["company"])


def _get_or_create(db: Session) -> CompanySettings:
    settings = db.get(CompanySettings, 1)
    if settings is None:
        settings = CompanySettings(id=1, company_name="InternFlow")
        db.add(settings)
        db.flush()
    return settings


def _out(settings: CompanySettings) -> CompanySettingsOut:
    result = CompanySettingsOut.model_validate(settings)
    result.logo_url = f"/api/v1/company/assets/{settings.logo_key}" if settings.logo_key else None
    return result


@router.get("/settings", response_model=CompanySettingsOut)
def get_settings(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return _out(_get_or_create(db))


@router.patch("/settings", response_model=CompanySettingsOut)
def update_settings(
    payload: CompanySettingsUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    settings = _get_or_create(db)
    updates = payload.model_dump(exclude_unset=True)
    for k, v in updates.items():
        setattr(settings, k, v)
    if updates:
        record_audit(db, admin, "company.update", metadata={"fields": list(updates.keys())})
    db.commit()
    db.refresh(settings)
    return _out(settings)


@router.post("/assets/upload")
async def upload_asset(
    kind: str,
    file: UploadFile,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Protected asset upload for logo, certificate template, and signatures."""
    folder_map = {
        "logo": "uploads",
        "certificate_template": "uploads",
        "signature_ceo": "signatures",
        "signature_instructor": "signatures",
    }
    if kind not in folder_map:
        raise HTTPException(status_code=400, detail="Unknown asset kind")
    content = await read_upload(file)
    key = storage.new_key(folder_map[kind], file.filename or kind)
    storage.save_bytes(key, content)

    settings = _get_or_create(db)
    column_map = {
        "logo": "logo_key",
        "certificate_template": "certificate_template_key",
        "signature_ceo": "signature_ceo_key",
        "signature_instructor": "signature_instructor_key",
    }
    setattr(settings, column_map[kind], key)
    record_audit(db, admin, f"company.upload_{kind}")
    db.commit()
    db.refresh(settings)
    return _out(settings)


@router.get("/assets/download")
def download_asset(
    key: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    content = storage.read_bytes(key)
    from fastapi.responses import Response

    return Response(content, media_type="application/octet-stream")