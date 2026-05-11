"""Password hashing (bcrypt) and JWT minting via FluxLit helpers."""

from __future__ import annotations

import os

from passlib.context import CryptContext

from fluxlit.auth.jwt import issue_hs256_access_token

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Demo defaults — set JWT_ISSUER / JWT_AUDIENCE / JWT_SECRET in production.
JWT_ISSUER = os.environ.get("JWT_ISSUER", "fullstack-demo")
JWT_AUDIENCE = os.environ.get("JWT_AUDIENCE", "fullstack-demo-api")
JWT_SECRET = os.environ.get(
    "JWT_SECRET",
    "fullstack-demo-jwt-secret-min-32-chars-for-hs256!!",
)
JWT_TTL_SECONDS = int(os.environ.get("JWT_TTL_SECONDS", "3600"))


def hash_password(plain: str) -> str:
    return _pwd.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd.verify(plain, hashed)


def mint_access_token(*, user_id: int, email: str, full_name: str) -> str:
    return issue_hs256_access_token(
        subject=str(user_id),
        issuer=JWT_ISSUER,
        audience=JWT_AUDIENCE,
        secret=JWT_SECRET,
        ttl_seconds=JWT_TTL_SECONDS,
        extra_claims={"email": email, "name": full_name, "scope": "read write"},
    )
