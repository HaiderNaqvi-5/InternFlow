from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR: Path = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=f"{ROOT_DIR}/.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: str = "development"
    APP_NAME: str = "InternFlow"
    API_PREFIX: str = "/api/v1"
    FRONTEND_URL: str = "http://localhost:5173"

    DATABASE_URL: str = (
        "postgresql+psycopg://internflow:internflow_dev@localhost:5432/internflow"
    )

    JWT_SECRET_KEY: str = "dev-only-9f2c1a4b7d3e6f8a5b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14

    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "no-reply@internflow.local"
    SMTP_USE_TLS: bool = True

    STORAGE_BACKEND: str = "local"
    UPLOAD_DIR: str = "storage"
    MAX_UPLOAD_SIZE_MB: int = 25

    S3_ENDPOINT_URL: str = ""
    S3_BUCKET: str = ""
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""

    VAPID_PUBLIC_KEY: str = ""
    VAPID_PRIVATE_KEY: str = ""
    VAPID_SUBJECT: str = "mailto:admin@internflow.local"

    CORS_ALLOWED_ORIGINS: str = "http://localhost:5173"

    LOG_LEVEL: str = "INFO"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ALLOWED_ORIGINS.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def upload_dir_path(self) -> Path:
        path = Path(self.UPLOAD_DIR)
        if not path.is_absolute():
            path = ROOT_DIR / path
        return path

    @property
    def max_upload_size_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @model_validator(mode="after")
    def _enforce_production_security(self):
        if not self.is_production:
            return self
        if len(self.JWT_SECRET_KEY) < 32:
            raise ValueError(
                "JWT_SECRET_KEY must be at least 32 characters in production"
            )
        if self.JWT_SECRET_KEY == "dev-secret-change-me":
            raise ValueError(
                "JWT_SECRET_KEY must be set to a non-default secret in production"
            )
        if self.CORS_ALLOWED_ORIGINS.strip() == "*":
            raise ValueError(
                "CORS_ALLOWED_ORIGINS must be an explicit origin list, not '*', in production"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()