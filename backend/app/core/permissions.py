from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import decode_token
from app.db.session import get_db
from app.models import User, UserRole

settings = get_settings()

bearer_scheme = HTTPBearer(auto_error=False)

# Endpoints an account with a pending first-login password setup may call.
EXEMPT_PATHS = {
    "/api/v1/auth/first-password",
    "/api/v1/auth/me",
    "/api/v1/auth/logout",
    "/api/v1/auth/refresh",
    "/api/v1/health",
}


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    payload = decode_token(credentials.credentials, expected_type="access")
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        )
    user = db.get(User, int(payload["sub"]))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account deactivated. Contact your administrator.",
        )
    if user.must_reset_password and request.url.path not in EXEMPT_PATHS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Password setup required before accessing the platform",
        )
    request.state.user = user
    request.state.db = db
    return user


def require_roles(*roles: UserRole):
    def _checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions for this operation",
            )
        return user

    return _checker


require_admin = require_roles(UserRole.ADMIN)
require_supervisor = require_roles(UserRole.SUPERVISOR)
require_supervisor_or_admin = require_roles(UserRole.SUPERVISOR, UserRole.ADMIN)
require_any_authenticated = require_roles(
    UserRole.ADMIN, UserRole.SUPERVISOR, UserRole.INTERN
)