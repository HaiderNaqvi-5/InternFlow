from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings

settings = get_settings()

password_hash = PasswordHash.recommended()
_ACCESS = "access"
_REFRESH = "refresh"


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    if not hashed:
        return False
    try:
        return password_hash.verify(password, hashed)
    except Exception:
        return False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_token(
    subject: str,
    token_type: str,
    expires_delta: timedelta | None = None,
    extra: dict | None = None,
) -> str:
    payload: dict = {
        "sub": str(subject),
        "type": token_type,
        "iat": _now(),
    }
    if expires_delta is not None:
        payload["exp"] = _now() + expires_delta
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(subject: str, role: str, extra: dict | None = None) -> str:
    expire = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    data = {"role": role}
    if extra:
        data.update(extra)
    return create_token(subject, _ACCESS, expires_delta=expire, extra=data)


def create_refresh_token(subject: str) -> str:
    import secrets

    expire = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    nonce = secrets.token_hex(16)
    return create_token(
        subject, _REFRESH, expires_delta=expire, extra={"jti": nonce}
    )


def decode_token(token: str, expected_type: str | None = None) -> dict | None:
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
    except jwt.PyJWTError:
        return None
    if expected_type and payload.get("type") != expected_type:
        return None
    return payload


def hash_token(token: str) -> str:
    import hashlib

    return hashlib.sha256(token.encode("utf-8")).hexdigest()