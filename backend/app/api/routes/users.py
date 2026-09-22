import secrets as pysecrets

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.permissions import get_current_user, require_admin, require_any_authenticated
from app.core.security import hash_password
from app.db.session import get_db
from app.models import BatchMembership, User, UserRole
from app.schemas.auth import (
    BulkUserAction,
    ImportPreview,
    Message,
    PaginatedUsers,
    ProfileUpdate,
    UserCreate,
    UserMe,
    UserOut,
    UserUpdate,
)
from app.services.access import get_intern_active_batch
from app.services.imports import preview_import, row_to_user
from app.utils.email import send_email
from app.utils.storage import storage

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=PaginatedUsers)
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str = "",
    role: str | None = None,
    active_only: bool = True,
    user: User = Depends(require_any_authenticated),
    db: Session = Depends(get_db),
):
    query = select(User)
    count_query = select(func.count(User.id))

    # Interns may only ever see themselves in directory listings
    if user.role == UserRole.INTERN:
        query = query.where(User.id == user.id)
        count_query = count_query.where(User.id == user.id)
    elif user.role == UserRole.SUPERVISOR:
        from app.services.access import get_supervised_batch_ids

        batch_ids = get_supervised_batch_ids(db, user.id)
        if not batch_ids:
            return PaginatedUsers(items=[], total=0, page=page, page_size=page_size)
        intern_ids = [
            r[0]
            for r in db.execute(
                select(BatchMembership.intern_id).where(
                    BatchMembership.batch_id.in_(batch_ids),
                    BatchMembership.is_active.is_(True),
                )
            )
        ]
        query = query.where(User.id.in_(intern_ids + [user.id]))
        count_query = count_query.where(User.id.in_(intern_ids + [user.id]))

    if active_only:
        query = query.where(User.is_active.is_(True))
        count_query = count_query.where(User.is_active.is_(True))
    if role:
        query = query.where(User.role == role)
        count_query = count_query.where(User.role == role)
    if search:
        like = f"%{search.strip()}%"
        cond = User.full_name.ilike(like) | User.email.ilike(like)
        query = query.where(cond)
        count_query = count_query.where(cond)

    total = db.execute(count_query).scalar() or 0
    items = db.execute(
        query.order_by(User.full_name)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()

    return PaginatedUsers(
        items=[UserOut.model_validate(u) for u in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=UserOut)
def create_user(
    payload: UserCreate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    existing = db.execute(
        select(User).where(User.email == payload.email.lower().strip())
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    role = UserRole(payload.role) if payload.role in ("intern", "supervisor", "admin") else UserRole.INTERN
    initial_pw = pysecrets.token_urlsafe(12)
    user = User(
        email=payload.email.lower().strip(),
        full_name=payload.full_name,
        role=role,
        must_reset_password=True,
        password_hash=hash_password(initial_pw),
        is_active=True,
    )
    db.add(user)
    db.flush()

    # If intern and batch_id provided, add to batch
    if payload.batch_id and role == UserRole.INTERN:
        membership = BatchMembership(batch_id=payload.batch_id, intern_id=user.id, is_active=True)
        db.add(membership)
        db.flush()

    record_audit(db, admin, "users.create", "user", user.id)
    send_email(
        to=user.email,
        subject="Your InternFlow account is ready",
        html_body=f"<p>Welcome, {user.full_name}!</p><p>Your account has been created. Log in with your email and set a password on first access.</p>",
    )
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.get("/{user_id}", response_model=UserOut)
def get_user(
    user_id: int,
    viewer: User = Depends(require_any_authenticated),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if viewer.role == UserRole.INTERN and viewer.id != user_id:
        raise HTTPException(status_code=403, detail="Cannot view other users")
    if viewer.role == UserRole.SUPERVISOR and viewer.id != user_id:
        from app.services.access import get_supervised_batch_ids

        allowed = set(get_supervised_batch_ids(db, viewer.id))
        if user.role == UserRole.INTERN:
            membership = db.execute(
                select(BatchMembership).where(
                    BatchMembership.intern_id == user_id,
                    BatchMembership.is_active.is_(True),
                )
            ).scalar_one_or_none()
            if membership is None or membership.batch_id not in allowed:
                raise HTTPException(
                    status_code=403, detail="Cannot view interns outside your batches"
                )
        else:
            raise HTTPException(
                status_code=403, detail="Cannot view supervisors or admins"
            )
    return UserOut.model_validate(user)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    updates = payload.model_dump(exclude_unset=True)
    if "is_active" in updates:
        record_audit(
            db, admin,
            "users.deactivate" if not updates["is_active"] else "users.activate",
            "user", user_id,
        )
    for k, v in updates.items():
        setattr(user, k, v)
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.delete("/{user_id}", response_model=Message)
def deactivate_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = False
    record_audit(db, admin, "users.deactivate", "user", user_id)
    db.commit()
    return Message(message="User deactivated")


@router.patch("/me/profile", response_model=UserMe)
def update_my_profile(
    payload: ProfileUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    updates = payload.model_dump(exclude_unset=True)
    for k, v in updates.items():
        setattr(user, k, v)
    db.commit()
    db.refresh(user)
    membership = get_intern_active_batch(db, user.id) if user.role == UserRole.INTERN else None
    data = UserMe.model_validate(user)
    if membership:
        from app.models import Batch

        batch = db.get(Batch, membership.batch_id)
        data.active_batch_id = batch.id if batch else None
        data.active_batch_name = batch.name if batch else None
    return data


@router.post("/me/avatar")
async def upload_avatar(
    file: UploadFile,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.utils.storage import read_upload

    content = await read_upload(file)
    key = storage.new_key("uploads", file.filename or "avatar")
    storage.save_bytes(key, content)
    user.avatar_key = key
    db.commit()
    return {"avatar_key": key}


@router.post("/import/preview", response_model=ImportPreview)
async def preview_user_import(
    file: UploadFile,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    from app.utils.storage import read_upload

    content = await read_upload(file)
    result = preview_import(db, content, file.filename or "upload.csv")
    result["filename"] = file.filename
    return ImportPreview(**result)


@router.post("/import/apply")
async def apply_user_import(
    file: UploadFile,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    from app.utils.storage import read_upload

    content = await read_upload(file)
    result = preview_import(db, content, file.filename or "upload.csv")
    created = 0
    errors: list[dict] = []
    for row in result["valid_rows"]:
        try:
            row_to_user(db, row)
            created += 1
        except Exception as e:
            errors.append({"email": row.get("email", ""), "error": str(e)})
    record_audit(
        db, admin, "users.bulk_import", metadata={"created": created, "errors": len(errors)}
    )
    db.commit()
    return {"created": created, "failed": errors}


@router.post("/bulk/deactivate", response_model=Message)
def bulk_deactivate_users(
    payload: BulkUserAction,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    for uid in payload.user_ids:
        user = db.get(User, uid)
        if user:
            user.is_active = False
    record_audit(
        db, admin, "users.bulk_deactivate",
        metadata={"user_ids": payload.user_ids},
    )
    db.commit()
    return Message(message=f"Processed {len(payload.user_ids)} users")