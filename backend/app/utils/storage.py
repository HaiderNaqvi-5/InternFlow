import mimetypes
import re
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.core.config import get_settings

settings = get_settings()

# Allowed upload types per the PRD (task/submission/reference material).
ALLOWED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".doc",
    ".zip",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".txt",
    ".md",
    ".csv",
    ".xlsx",
    ".svg",
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".html",
    ".css",
    ".json",
    ".sql",
}

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}


def allowed_extension(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def sanitize_filename(filename: str) -> str:
    name = Path(filename).name
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return name or "file"


class StorageService:
    """Abstraction for file storage. Local backend for dev; object-storage
    compatible in production without changing business logic."""

    def __init__(self) -> None:
        self.backend = settings.STORAGE_BACKEND
        self.root = settings.upload_dir_path

    def _resolve(self, relative_key: str) -> Path:
        return (self.root / relative_key).resolve()

    def save_bytes(self, relative_key: str, content: bytes) -> str:
        if self.backend in ("s3", "object"):
            raise NotImplementedError(
                "S3 backend requires production credentials; configured storage "
                "backend is not locally available."
            )
        path = self._resolve(relative_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return relative_key

    def read_bytes(self, relative_key: str) -> bytes:
        if self.backend in ("s3", "object"):
            raise NotImplementedError("S3 backend not available locally.")
        path = self._resolve(relative_key)
        if not path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        return path.read_bytes()

    def exists(self, relative_key: str) -> bool:
        return self._resolve(relative_key).exists() if self.backend != "s3" else False

    def delete(self, relative_key: str) -> None:
        if self.backend in ("s3", "object"):
            return
        path = self._resolve(relative_key)
        if path.exists():
            path.unlink()

    def new_key(self, folder: str, original_name: str) -> str:
        safe = sanitize_filename(original_name)
        stem = Path(safe).stem
        ext = Path(safe).suffix
        return f"{folder}/{uuid.uuid4().hex}_{stem}{ext}"


storage = StorageService()


def validate_upload(upload: UploadFile) -> None:
    original_name = upload.filename or "file"
    if not allowed_extension(original_name):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"File type not allowed: {Path(original_name).suffix}",
        )


async def read_upload(upload: UploadFile) -> bytes:
    validate_upload(upload)
    content = await upload.read()
    if len(content) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the {settings.MAX_UPLOAD_SIZE_MB} MB limit",
        )
    return content


def guess_content_type(filename: str) -> str:
    ctype, _ = mimetypes.guess_type(filename)
    return ctype or "application/octet-stream"