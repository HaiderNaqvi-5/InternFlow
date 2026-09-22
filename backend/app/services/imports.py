import csv
import io
import re

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User, UserRole

EXPECTED_HEADERS = ["email", "full_name", "role"]


class ParsedRow:
    def __init__(self, row_number: int, email: str = "", full_name: str = "", role: str = "intern"):
        self.row_number = row_number
        self.email = email.strip().lower()
        self.full_name = full_name.strip()
        self.role = role.strip().lower() if role else "intern"


def _normalize_header(header: str) -> str:
    return header.strip().lower().replace(" ", "_").replace("-", "_")


def parse_table(content: bytes, filename: str) -> list[list[str]]:
    name = filename.lower()
    if name.endswith(".csv"):
        text = content.decode("utf-8-sig", errors="replace")
        return list(csv.reader(io.StringIO(text)))
    if name.endswith((".xlsx", ".xlsm")):
        import openpyxl

        workbook = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
        sheet = workbook.active
        rows: list[list[str]] = []
        for row in sheet.iter_rows(values_only=True):
            rows.append(["" if cell is None else str(cell) for cell in row])
        return rows
    raise HTTPException(status_code=415, detail="Only CSV or Excel files are supported")


def validate_row(row: ParsedRow, seen_emails: set[str], existing_emails: set[str]) -> str | None:
    if not row.email:
        return "Email is required"
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", row.email):
        return "Invalid email format"
    if not row.full_name:
        return "Full name is required"
    if row.role not in ("intern", "supervisor", "admin"):
        return "Role must be intern, supervisor or admin"
    if row.email in seen_emails:
        return "Duplicate email within file"
    if row.email in existing_emails:
        return "Email already registered"
    return None


def preview_import(db: Session, content: bytes, filename: str) -> dict:
    rows = parse_table(content, filename)
    if len(rows) < 2:
        raise HTTPException(status_code=400, detail="File must contain a header row and data")

    header = [_normalize_header(h) for h in rows[0]]
    if not all(h in header for h in EXPECTED_HEADERS):
        raise HTTPException(
            status_code=400,
            detail=f"Missing required columns. Expected: {', '.join(EXPECTED_HEADERS)}",
        )

    idx = {h: i for i, h in enumerate(header)}
    existing = set(
        db.execute(select(User.email)).scalars()
    )
    seen: set[str] = set()
    valid_rows: list[dict] = []
    failed_rows: list[dict] = []

    for row_number, row in enumerate(rows[1:], start=2):
        if not any(cell.strip() for cell in row):
            continue
        parsed = ParsedRow(
            row_number,
            email=row[idx["email"]],
            full_name=row[idx["full_name"]],
            role=row[idx["role"]] if "role" in idx else "intern",
        )
        error = validate_row(parsed, seen, existing)
        if error:
            failed_rows.append(
                {"row_number": row_number, "error": error, "email": parsed.email}
            )
        else:
            seen.add(parsed.email)
            valid_rows.append(
                {
                    "row_number": row_number,
                    "email": parsed.email,
                    "full_name": parsed.full_name,
                    "role": parsed.role,
                }
            )

    return {"valid_count": len(valid_rows), "failed_count": len(failed_rows), "valid_rows": valid_rows, "failed_rows": failed_rows}


def row_to_user(db: Session, row: dict) -> User:

    user = User(
        email=row["email"],
        full_name=row["full_name"],
        role=UserRole(row["role"]),
        must_reset_password=True,
        password_hash=None,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user