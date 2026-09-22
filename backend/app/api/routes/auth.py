from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.config import get_settings
from app.core.permissions import get_current_user
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.db.session import get_db
from app.models import User, UserRole
from app.schemas.auth import (
    AuthResponse,
    FirstPasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    ResetPasswordRequest,
    UserMe,
)
from app.services.access import get_intern_active_batch
from app.utils.email import send_email

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_tokens(db: Session, user: User) -> dict:
    access = create_access_token(user.id, user.role.value)
    refresh = create_refresh_token(user.id)
    from app.models import RefreshToken

    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_token(refresh),
            expires_at=__import__("datetime").datetime.utcnow()
            + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "must_reset_password": user.must_reset_password,
    }


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.execute(
        select(User).where(User.email == payload.email.lower().strip())
    ).scalar_one_or_none()
    if user is None or not user.password_hash or not verify_password(
        payload.password, user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account deactivated. Contact your administrator.",
        )
    tokens = _issue_tokens(db, user)
    record_audit(db, user, "auth.login", "user", user.id)
    db.commit()
    return tokens


@router.post("/first-password", response_model=AuthResponse)
def first_password(payload: FirstPasswordRequest, db: Session = Depends(get_db)):
    """Set a password on first login. Requires the current (initial) password."""
    user = db.execute(
        select(User).where(User.email == payload.email.lower().strip())
    ).scalar_one_or_none()
    if user is None or not user.password_hash or not verify_password(
        payload.current_password, user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or current password",
        )
    user.password_hash = hash_password(payload.new_password)
    user.must_reset_password = False
    record_audit(db, user, "auth.first_password_set", "user", user.id)
    tokens = _issue_tokens(db, user)
    db.commit()
    return tokens


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    from app.core.security import create_token

    user = db.execute(
        select(User).where(User.email == payload.email.lower().strip())
    ).scalar_one_or_none()
    if user is not None:
        token = create_token(
            str(user.id), "reset", timedelta(minutes=30)
        )
        reset_link = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password?token={token}"
        send_email(
            to=user.email,
            subject="Reset your InternFlow password",
            html_body=f"<p>Hi {user.full_name},</p><p>A password reset was requested. Click the link below to set a new password:</p><p><a href='{reset_link}'>{reset_link}</a></p><p>This link expires in 30 minutes. If you did not request this, ignore this email.</p>",
            text_body=f"Hi {user.full_name},\n\nReset your InternFlow password using this link (expires in 30 minutes):\n{reset_link}",
        )
    return {"message": "If that email exists, a reset link has been sent."}


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    payload_data = decode_token(payload.token, expected_type="reset")
    if payload_data is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )
    user = db.get(User, int(payload_data["sub"]))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.password_hash = hash_password(payload.new_password)
    user.must_reset_password = False
    record_audit(db, user, "auth.password_reset", "user", user.id)
    db.commit()
    return {"message": "Password has been reset. You can now log in."}


@router.post("/refresh", response_model=AuthResponse)
def refresh(payload: dict, db: Session = Depends(get_db)):
    refresh_token = payload.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="refresh_token is required"
        )
    from app.models import RefreshToken

    data = decode_token(refresh_token, expected_type="refresh")
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )
    row = db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_token(refresh_token)
        )
    ).scalar_one_or_none()
    if row is None or row.revoked or row.expires_at < __import__("datetime").datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Expired refresh token"
        )
    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User unavailable")
    row.revoked = True
    tokens = _issue_tokens(db, user)
    db.commit()
    return tokens


@router.post("/logout")
def logout(payload: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.models import RefreshToken

    refresh_token = payload.get("refresh_token")
    if refresh_token:
        row = db.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == hash_token(refresh_token),
                RefreshToken.user_id == user.id,
            )
        ).scalar_one_or_none()
        if row:
            row.revoked = True
    record_audit(db, user, "auth.logout", "user", user.id)
    db.commit()
    return {"message": "Logged out"}


@router.get("/me", response_model=UserMe)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    membership = get_intern_active_batch(db, user.id) if user.role == UserRole.INTERN else None
    data = UserMe.model_validate(user)
    if membership:
        from app.models import Batch

        batch = db.get(Batch, membership.batch_id)
        data.active_batch_id = batch.id if batch else None
        data.active_batch_name = batch.name if batch else None
    return data