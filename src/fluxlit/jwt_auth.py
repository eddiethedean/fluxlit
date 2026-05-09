"""JWT bearer validation for FastAPI (requires ``pip install 'fluxlit[auth]'``).

Uses PyJWT with optional :class:`jwt.PyJWKClient` for JWKS (RS256/ES256) or HS256 for development.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, cast

from fastapi import HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

_MISSING_AUTH_EXTRA_MSG = (
    "JWT support requires optional dependencies. Install with: pip install 'fluxlit[auth]'"
)


def _require_pyjwt() -> Any:
    try:
        import jwt
    except ImportError as e:
        raise RuntimeError(_MISSING_AUTH_EXTRA_MSG) from e
    return jwt


class StandardClaims(BaseModel):
    """Common JWT claims plus extra keys from the token payload."""

    model_config = ConfigDict(extra="allow")

    sub: str | None = None
    iss: str | None = None
    aud: str | list[str] | None = None
    exp: int | None = None
    iat: int | None = None
    nbf: int | None = None
    jti: str | None = None
    scope: str | None = Field(default=None, description="OAuth2 space-delimited scopes (optional).")


@dataclass
class JWTAuthConfig:
    """Configuration for :class:`JWTBearer`."""

    issuer: str
    audience: str | list[str]
    algorithms: list[str] = field(default_factory=lambda: ["RS256"])
    jwks_url: str | None = None
    """JWKS URI (required for asymmetric algorithms unless using HS256-only)."""

    hs256_secret: str | None = None
    """If set, tokens are validated with HS256 using this secret (development)."""

    leeway_seconds: int = 0


class JWTBearer:
    """FastAPI dependency: validate ``Authorization: Bearer`` and return :class:`StandardClaims`."""

    def __init__(self, config: JWTAuthConfig) -> None:
        self._config = config
        self._jwks_client: Any = None
        if config.hs256_secret:
            if "HS256" not in config.algorithms:
                msg = "hs256_secret requires HS256 in algorithms"
                raise ValueError(msg)
        elif config.jwks_url:
            jwt_mod = _require_pyjwt()
            self._jwks_client = jwt_mod.PyJWKClient(config.jwks_url)
        else:
            msg = "Either hs256_secret (HS256) or jwks_url (asymmetric) must be set"
            raise ValueError(msg)

    async def __call__(self, request: Request) -> StandardClaims:
        auth = request.headers.get("authorization")
        if not auth or not auth.lower().startswith("bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing bearer token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        token = auth[7:].strip()
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Empty bearer token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        jwt_mod = _require_pyjwt()
        try:
            if self._config.hs256_secret is not None:
                decoded = jwt_mod.decode(
                    token,
                    self._config.hs256_secret,
                    algorithms=self._config.algorithms,
                    audience=self._config.audience,
                    issuer=self._config.issuer,
                    leeway=self._config.leeway_seconds,
                    options={"require": ["exp"]},
                )
            else:
                assert self._jwks_client is not None
                signing_key = self._jwks_client.get_signing_key_from_jwt(token)
                decoded = jwt_mod.decode(
                    token,
                    signing_key.key,
                    algorithms=self._config.algorithms,
                    audience=self._config.audience,
                    issuer=self._config.issuer,
                    leeway=self._config.leeway_seconds,
                    options={"require": ["exp"]},
                )
        except jwt_mod.ExpiredSignatureError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired",
                headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
            ) from e
        except jwt_mod.InvalidTokenError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
            ) from e
        return StandardClaims.model_validate(decoded)


def _claims_scopes(claims: StandardClaims, scope_claim: str) -> set[str]:
    data = claims.model_dump(mode="python")
    raw = data.get(scope_claim)
    if raw is None:
        return set()
    if isinstance(raw, list):
        return {str(x) for x in raw}
    if isinstance(raw, str):
        return set(raw.split())
    return set()


def _claims_roles(claims: StandardClaims, roles_claim: str) -> set[str]:
    data = claims.model_dump(mode="python")
    raw = data.get(roles_claim)
    if raw is None:
        return set()
    if isinstance(raw, list):
        return {str(x) for x in raw}
    if isinstance(raw, str):
        return {raw}
    return set()


class RequireScopes:
    """Dependency factory: require OAuth2-style scopes (space-delimited or list claim)."""

    def __init__(
        self,
        bearer: JWTBearer,
        *scopes: str,
        scope_claim: str = "scope",
    ) -> None:
        self._bearer = bearer
        self._required = frozenset(scopes)
        self._scope_claim = scope_claim

    async def __call__(self, request: Request) -> StandardClaims:
        claims = await self._bearer(request)
        present = _claims_scopes(claims, self._scope_claim)
        if not self._required.issubset(present):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient scope",
            )
        return claims


class RequireRoles:
    """Dependency factory: require at least one role from a claim (string or list)."""

    def __init__(
        self,
        bearer: JWTBearer,
        *roles: str,
        roles_claim: str = "roles",
    ) -> None:
        self._bearer = bearer
        self._required = frozenset(roles)
        self._roles_claim = roles_claim

    async def __call__(self, request: Request) -> StandardClaims:
        claims = await self._bearer(request)
        present = _claims_roles(claims, self._roles_claim)
        if not self._required.intersection(present):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role",
            )
        return claims


def issue_hs256_access_token(
    *,
    subject: str,
    issuer: str,
    audience: str | list[str],
    secret: str,
    ttl_seconds: int,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Mint a short-lived HS256 JWT (BFF / dev only — keep ``secret`` server-side)."""
    jwt_mod = _require_pyjwt()
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "iss": issuer,
        "aud": audience,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)
    return cast(str, jwt_mod.encode(payload, secret, algorithm="HS256"))
