from tests.conftest import PASSWORD


def test_login_and_me(client):
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "supervisor@internflow.dev", "password": PASSWORD},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]

    me = client.get("/api/v1/auth/me", headers=auth_header(body["access_token"]))
    assert me.status_code == 200
    assert me.json()["role"] == "supervisor"


def test_supervisor_login_requires_first_password(auth):
    assert auth("intern1@internflow.dev")


def test_bad_login_rejected(client):
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@internflow.dev", "password": "wrong"},
    )
    assert r.status_code == 401


def test_unauthenticated_me_rejected(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_roles_cross_boundary(auth, client):
    intern = auth("intern1@internflow.dev")
    r = client.get("/api/v1/users", headers=intern)
    assert r.status_code == 200
    rows = r.json()["items"]
    assert len(rows) == 1 and rows[0]["role"] == "intern"


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}