import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.db.seed import seed  # noqa: E402
from app.main import app  # noqa: E402

PASSWORD = "Demo1234!"


@pytest.fixture(scope="session", autouse=True)
def reset_db():
    """Fresh deterministic schema + seed for the whole run."""
    from sqlalchemy import inspect, text

    from app.db.base import Base
    from app.db.session import engine

    insp = inspect(engine)
    with engine.begin() as conn:
        for table in reversed(insp.get_table_names()):
            conn.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))
    Base.metadata.create_all(engine)
    seed()


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def tokens(client):
    out = {}
    for email in ("admin@internflow.dev", "supervisor@internflow.dev", "intern1@internflow.dev",
                  "intern2@internflow.dev"):
        r = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
        assert r.status_code == 200, (email, r.text)
        out[email] = r.json()["access_token"]
    return out


@pytest.fixture
def auth(tokens):
    def _make(email):
        return {"Authorization": f"Bearer {tokens[email]}"}

    return _make