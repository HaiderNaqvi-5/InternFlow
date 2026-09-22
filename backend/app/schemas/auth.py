from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ApiError(BaseModel):
    detail: str


class Message(BaseModel):
    message: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AuthResponse(TokenPair):
    must_reset_password: bool = False


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class FirstPasswordRequest(BaseModel):
    email: EmailStr
    current_password: str
    new_password: str = Field(min_length=8)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8)


class RefreshRequest(BaseModel):
    refresh_token: str


class UserBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    role: str
    is_active: bool
    must_reset_password: bool
    avatar_key: str | None = None
    github_url: str | None = None
    linkedin_url: str | None = None
    bio: str | None = None
    phone: str | None = None


class UserOut(UserBrief):
    created_at: datetime


class ProfileUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    bio: str | None = None
    github_url: str | None = None
    linkedin_url: str | None = None
    skills: list[str] | None = None


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    role: str = "intern"
    batch_id: int | None = None


class UserUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    bio: str | None = None
    github_url: str | None = None
    linkedin_url: str | None = None
    skills: list[str] | None = None
    is_active: bool | None = None


class UserMe(UserOut):
    active_batch_id: int | None = None
    active_batch_name: str | None = None


class ImportPreview(BaseModel):
    filename: str
    valid_count: int
    failed_count: int
    valid_rows: list[dict]
    failed_rows: list[dict]


class BulkUserAction(BaseModel):
    user_ids: list[int]
    deactivate: bool = True


class PaginatedUsers(BaseModel):
    items: list[UserOut]
    total: int
    page: int
    page_size: int