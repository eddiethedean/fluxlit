"""Auth API tests via :class:`fluxlit.testing.FluxLitTestClient` (gateway + ``/api`` prefix)."""

from __future__ import annotations

from security import JWT_AUDIENCE, JWT_ISSUER, JWT_SECRET, JWT_TTL_SECONDS

from fluxlit.auth.jwt import issue_hs256_access_token
from fluxlit.testing import FluxLitTestClient


def test_register_login_and_me(fluxlit_client: FluxLitTestClient) -> None:
    r = fluxlit_client.api_post(
        "/auth/register",
        json={
            "email": "alice@example.com",
            "full_name": "Alice",
            "password": "hunter2hunter2",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "alice@example.com"
    assert body["full_name"] == "Alice"
    assert "id" in body

    r2 = fluxlit_client.api_post(
        "/auth/login",
        json={"email": "alice@example.com", "password": "hunter2hunter2"},
    )
    assert r2.status_code == 200
    token = r2.json()["access_token"]
    assert token

    r3 = fluxlit_client.api_get(
        "/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r3.status_code == 200
    me = r3.json()
    assert me["email"] == "alice@example.com"
    assert me["full_name"] == "Alice"
    assert me["sub"] == str(body["id"])


def test_register_duplicate_email(fluxlit_client: FluxLitTestClient) -> None:
    payload = {
        "email": "dup@example.com",
        "full_name": "One",
        "password": "passwordpassword",
    }
    assert fluxlit_client.api_post("/auth/register", json=payload).status_code == 201
    r = fluxlit_client.api_post("/auth/register", json={**payload, "full_name": "Two"})
    assert r.status_code == 409
    assert r.json()["detail"] == "Email already registered"


def test_login_unknown_user(fluxlit_client: FluxLitTestClient) -> None:
    r = fluxlit_client.api_post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "passwordpassword"},
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid email or password"


def test_login_wrong_password(fluxlit_client: FluxLitTestClient) -> None:
    fluxlit_client.api_post(
        "/auth/register",
        json={
            "email": "bob@example.com",
            "full_name": "Bob",
            "password": "correcthorsebatterystaple",
        },
    )
    r = fluxlit_client.api_post(
        "/auth/login",
        json={"email": "bob@example.com", "password": "wrongpassword"},
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid email or password"


def test_users_me_requires_bearer(fluxlit_client: FluxLitTestClient) -> None:
    r = fluxlit_client.api_get("/users/me")
    assert r.status_code == 401


def test_users_me_rejects_bad_token(fluxlit_client: FluxLitTestClient) -> None:
    r = fluxlit_client.api_get(
        "/users/me",
        headers={"Authorization": "Bearer not-a-jwt"},
    )
    assert r.status_code == 401


def test_users_me_rejects_wrong_issuer(fluxlit_client: FluxLitTestClient) -> None:
    bad = issue_hs256_access_token(
        subject="1",
        issuer="not-the-demo-issuer",
        audience=JWT_AUDIENCE,
        secret=JWT_SECRET,
        ttl_seconds=60,
    )
    r = fluxlit_client.api_get("/users/me", headers={"Authorization": f"Bearer {bad}"})
    assert r.status_code == 401


def test_users_me_rejects_wrong_audience(fluxlit_client: FluxLitTestClient) -> None:
    bad = issue_hs256_access_token(
        subject="1",
        issuer=JWT_ISSUER,
        audience="other-audience",
        secret=JWT_SECRET,
        ttl_seconds=60,
    )
    r = fluxlit_client.api_get("/users/me", headers={"Authorization": f"Bearer {bad}"})
    assert r.status_code == 401


def test_health_db(fluxlit_client: FluxLitTestClient) -> None:
    r = fluxlit_client.api_get("/health/db")
    assert r.status_code == 200
    assert r.json() == {"database": "ok"}


def test_register_email_normalized_to_lower(fluxlit_client: FluxLitTestClient) -> None:
    r = fluxlit_client.api_post(
        "/auth/register",
        json={
            "email": "User@Example.COM",
            "full_name": "Pat",
            "password": "passwordpassword",
        },
    )
    assert r.status_code == 201
    assert r.json()["email"] == "user@example.com"
    r2 = fluxlit_client.api_post(
        "/auth/login",
        json={"email": "USER@EXAMPLE.COM", "password": "passwordpassword"},
    )
    assert r2.status_code == 200


def test_register_validation_invalid_email(fluxlit_client: FluxLitTestClient) -> None:
    r = fluxlit_client.api_post(
        "/auth/register",
        json={
            "email": "not-an-email",
            "full_name": "X",
            "password": "passwordpassword",
        },
    )
    assert r.status_code == 422


def test_register_validation_short_password(fluxlit_client: FluxLitTestClient) -> None:
    r = fluxlit_client.api_post(
        "/auth/register",
        json={
            "email": "x@example.com",
            "full_name": "X",
            "password": "short",
        },
    )
    assert r.status_code == 422


def test_login_validation_missing_password(fluxlit_client: FluxLitTestClient) -> None:
    r = fluxlit_client.api_post(
        "/auth/login",
        json={"email": "any@example.com"},
    )
    assert r.status_code == 422


def test_token_response_shape(fluxlit_client: FluxLitTestClient) -> None:
    fluxlit_client.api_post(
        "/auth/register",
        json={
            "email": "tok@example.com",
            "full_name": "T",
            "password": "passwordpassword",
        },
    )
    r = fluxlit_client.api_post(
        "/auth/login",
        json={"email": "tok@example.com", "password": "passwordpassword"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == JWT_TTL_SECONDS
    assert isinstance(data["access_token"], str) and len(data["access_token"]) > 20
