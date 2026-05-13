"""Generic OIDC client and BFF-style auth routes.

Install ``fluxlit[auth]`` for JWT signing used by the BFF exchange.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
import warnings
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import urlencode, urlparse, urlunparse

import httpx
from fastapi import APIRouter, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from fluxlit.auth.jwt import _require_pyjwt, issue_hs256_access_token


class OIDCProvider(Protocol):
    """Minimal OIDC surface for discovery and token exchange."""

    @property
    def issuer(self) -> str: ...

    def authorization_url(
        self,
        *,
        redirect_uri: str,
        state: str,
        code_challenge: str,
        scope: str | None = None,
    ) -> str: ...

    def exchange_code(
        self,
        *,
        code: str,
        code_verifier: str,
        redirect_uri: str,
    ) -> dict[str, Any]: ...


class OIDCDiscoveryDocument(BaseModel):
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str


def pkce_pair() -> tuple[str, str]:
    """Return ``(code_verifier, code_challenge)`` for PKCE (S256)."""
    verifier = secrets.token_urlsafe(48)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


class OIDCBFFTokenStore(Protocol):
    """Storage for OIDC BFF PKCE ``state`` and one-time ``auth_code`` exchange payloads.

    Defaults to :class:`InMemoryOIDCBFFTokenStore` (process memory). Multi-replica API
    deployments should inject a shared implementation (for example Redis with TTL).
    """

    def save_pkce_verifier(self, state: str, code_verifier: str, *, now: float) -> None: ...

    def pop_pkce_verifier(self, state: str, *, now: float) -> str | None: ...

    def save_exchange_token(self, auth_code: str, access_token: str, *, now: float) -> None: ...

    def pop_exchange_token(self, auth_code: str, *, now: float) -> str | None: ...


@dataclass
class GenericOIDCClientConfig:
    issuer: str
    client_id: str
    client_secret: str
    http_timeout: float = 30.0


class GenericOIDCClient:
    """OIDC provider using ``/.well-known/openid-configuration`` (Authorization Code + PKCE)."""

    def __init__(self, config: GenericOIDCClientConfig) -> None:
        self._config = config
        self._doc: OIDCDiscoveryDocument | None = None

    @property
    def issuer(self) -> str:
        if self._doc:
            return self._doc.issuer
        return self._config.issuer.rstrip("/")

    def load_discovery_sync(self) -> None:
        url = f"{self._config.issuer.rstrip('/')}/.well-known/openid-configuration"
        with httpx.Client(timeout=self._config.http_timeout) as client:
            r = client.get(url)
            r.raise_for_status()
            self._doc = OIDCDiscoveryDocument.model_validate(r.json())

    def _require_doc(self) -> OIDCDiscoveryDocument:
        if self._doc is None:
            msg = "Call load_discovery_sync() before using the OIDC client"
            raise RuntimeError(msg)
        return self._doc

    def authorization_url(
        self,
        *,
        redirect_uri: str,
        state: str,
        code_challenge: str,
        scope: str | None = None,
    ) -> str:
        doc = self._require_doc()
        q = {
            "response_type": "code",
            "client_id": self._config.client_id,
            "redirect_uri": redirect_uri,
            "scope": scope or "openid profile email",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        return f"{doc.authorization_endpoint}?{urlencode(q)}"

    def exchange_code(
        self,
        *,
        code: str,
        code_verifier: str,
        redirect_uri: str,
    ) -> dict[str, Any]:
        doc = self._require_doc()
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": self._config.client_id,
            "client_secret": self._config.client_secret,
            "code_verifier": code_verifier,
        }
        with httpx.Client(timeout=self._config.http_timeout) as client:
            r = client.post(
                doc.token_endpoint,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            r.raise_for_status()
            parsed = r.json()
            if not isinstance(parsed, dict):
                msg = "Token endpoint returned non-object JSON"
                raise ValueError(msg)
            return parsed


@dataclass
class OIDCBFFConfig:
    """Settings for :func:`register_oidc_bff_routes`."""

    oidc: OIDCProvider
    first_party_secret: str
    token_issuer: str = "fluxlit-bff"
    token_audience: str = "fluxlit-app"
    access_token_ttl_seconds: int = 3600
    public_base_url: str = ""
    """Origin only, e.g. ``https://app.example.com`` (no trailing slash)."""

    login_path: str = "/auth/login"
    callback_path: str = "/auth/callback"
    exchange_path: str = "/auth/exchange"
    scope: str = "openid profile email"

    streamlit_redirect_path: str = "/"
    """Browser path to send the user to with a one-time ``auth_code`` query param."""

    state_ttl_seconds: int = 600
    otc_ttl_seconds: int = 120

    id_token_audience: str = ""
    """Expected ``aud`` for ``id_token`` validation.

    If empty, ``client_id`` from :class:`GenericOIDCClient` is used.
    """

    id_token_leeway_seconds: int = 0
    """Clock skew leeway (seconds) when validating ``id_token`` with JWKS."""

    allow_unverified_id_token_for_custom_oidc: bool = False
    """If True, allow non-:class:`GenericOIDCClient` providers to use parse-only ``sub``.

    Default ``False``: custom :class:`OIDCProvider` callbacks reject minting tokens from
    ``id_token`` without JWKS verification. Set ``True`` only when the provider verifies
    tokens before returning them, or for tests.
    """

    bff_token_store: OIDCBFFTokenStore | None = None
    """Optional shared storage for PKCE ``state`` and one-time ``auth_code`` values.

    When ``None``, :func:`register_oidc_bff_routes` uses :class:`InMemoryOIDCBFFTokenStore`
    with :attr:`state_ttl_seconds` and :attr:`otc_ttl_seconds` (single replica).
    """


def _purge_expired(store: dict[str, tuple[str, float]], ttl: float, now: float) -> None:
    expired = [k for k, (_, t0) in store.items() if now - t0 > ttl]
    for k in expired:
        del store[k]


@dataclass
class InMemoryOIDCBFFTokenStore:
    """Process-local PKCE and exchange storage (default for :class:`OIDCBFFConfig`)."""

    _pkce: dict[str, tuple[str, float]] = field(default_factory=dict)
    _exchange: dict[str, tuple[str, float]] = field(default_factory=dict)
    state_ttl_seconds: float = 600.0
    otc_ttl_seconds: float = 120.0

    def save_pkce_verifier(self, state: str, code_verifier: str, *, now: float) -> None:
        _purge_expired(self._pkce, self.state_ttl_seconds, now)
        self._pkce[state] = (code_verifier, now)

    def pop_pkce_verifier(self, state: str, *, now: float) -> str | None:
        _purge_expired(self._pkce, self.state_ttl_seconds, now)
        entry = self._pkce.pop(state, None)
        return None if entry is None else entry[0]

    def save_exchange_token(self, auth_code: str, access_token: str, *, now: float) -> None:
        _purge_expired(self._exchange, self.otc_ttl_seconds, now)
        self._exchange[auth_code] = (access_token, now)

    def pop_exchange_token(self, auth_code: str, *, now: float) -> str | None:
        _purge_expired(self._exchange, self.otc_ttl_seconds, now)
        entry = self._exchange.pop(auth_code, None)
        return None if entry is None else entry[0]


class ExchangeBody(BaseModel):
    code: str = Field(min_length=8)


def register_oidc_bff_routes(
    app: FastAPI,
    config: OIDCBFFConfig,
    *,
    router_prefix: str = "",
) -> APIRouter:
    """Attach login, OAuth callback, and Streamlit-friendly token exchange routes."""
    if not (config.public_base_url or "").strip():
        warnings.warn(
            (
                "OIDCBFFConfig.public_base_url is empty: OAuth redirect_uri and post-login "
                "URLs use request.base_url, which can be wrong behind proxies. Set "
                "public_base_url or FLUXLIT_PUBLIC_BASE_URL in production."
            ),
            stacklevel=2,
        )
    router = APIRouter(prefix=router_prefix, tags=["auth"])
    token_store = config.bff_token_store or InMemoryOIDCBFFTokenStore(
        state_ttl_seconds=float(config.state_ttl_seconds),
        otc_ttl_seconds=float(config.otc_ttl_seconds),
    )

    def redirect_uri(request: Request) -> str:
        base = (config.public_base_url or str(request.base_url)).rstrip("/")
        cb = config.callback_path
        path = cb if cb.startswith("/") else f"/{cb}"
        return f"{base}{path}"

    @router.get(config.login_path)
    def login(request: Request) -> Any:
        from fastapi.responses import RedirectResponse

        verifier, challenge = pkce_pair()
        state = secrets.token_urlsafe(32)
        now = time.monotonic()
        token_store.save_pkce_verifier(state, verifier, now=now)
        url = config.oidc.authorization_url(
            redirect_uri=redirect_uri(request),
            state=state,
            code_challenge=challenge,
            scope=config.scope,
        )
        return RedirectResponse(url, status_code=302)

    @router.get(config.callback_path)
    def callback(request: Request, code: str = "", state: str = "") -> Any:
        from fastapi.responses import RedirectResponse

        if not code or not state:
            raise HTTPException(status_code=400, detail="Missing code or state")
        now = time.monotonic()
        verifier = token_store.pop_pkce_verifier(state, now=now)
        if verifier is None:
            raise HTTPException(status_code=400, detail="Invalid or expired state")
        tokens = config.oidc.exchange_code(
            code=code,
            code_verifier=verifier,
            redirect_uri=redirect_uri(request),
        )
        id_token = tokens.get("id_token")
        if not isinstance(id_token, str) or not id_token:
            raise HTTPException(status_code=502, detail="IdP response missing id_token")
        sub = _resolve_id_token_sub(id_token=id_token, config=config)
        access = issue_hs256_access_token(
            subject=sub,
            issuer=config.token_issuer,
            audience=config.token_audience,
            secret=config.first_party_secret,
            ttl_seconds=config.access_token_ttl_seconds,
        )
        otc = secrets.token_urlsafe(32)
        now = time.monotonic()
        token_store.save_exchange_token(otc, access, now=now)
        dest = _with_query(
            base=(config.public_base_url or str(request.base_url)).rstrip("/"),
            path=config.streamlit_redirect_path,
            query={"auth_code": otc},
        )
        return RedirectResponse(dest, status_code=302)

    @router.post(config.exchange_path)
    def exchange(body: ExchangeBody) -> dict[str, str]:
        now = time.monotonic()
        token = token_store.pop_exchange_token(body.code, now=now)
        if token is None:
            raise HTTPException(status_code=401, detail="Invalid or expired auth code")
        return {"access_token": token, "token_type": "bearer"}

    app.include_router(router)
    return router


def _verify_id_token_jwks(
    *,
    id_token: str,
    issuer: str,
    jwks_uri: str,
    audience: str,
    leeway: int = 0,
) -> str:
    """Validate ``id_token`` signature and claims via IdP JWKS; return ``sub``."""
    jwt_mod = _require_pyjwt()
    jwks_client = jwt_mod.PyJWKClient(jwks_uri)
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(id_token)
        payload = jwt_mod.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256", "ES256", "ES384", "ES512"],
            audience=audience,
            issuer=issuer,
            leeway=leeway,
            options={"require": ["exp", "sub"]},
        )
    except jwt_mod.InvalidTokenError as e:
        raise HTTPException(status_code=502, detail="Invalid id_token") from e
    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub:
        raise HTTPException(status_code=502, detail="id_token missing sub")
    return sub


def _resolve_id_token_sub(*, id_token: str, config: OIDCBFFConfig) -> str:
    """Return ``sub`` from ``id_token`` (JWKS path for :class:`GenericOIDCClient`)."""
    oidc = config.oidc
    if isinstance(oidc, GenericOIDCClient):
        doc = oidc._require_doc()
        aud = (config.id_token_audience or "").strip() or oidc._config.client_id
        iss = oidc.issuer.rstrip("/")
        return _verify_id_token_jwks(
            id_token=id_token,
            issuer=iss,
            jwks_uri=doc.jwks_uri,
            audience=aud,
            leeway=config.id_token_leeway_seconds,
        )
    if not config.allow_unverified_id_token_for_custom_oidc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Custom OIDCProvider requires JWKS validation via GenericOIDCClient, or set "
                "OIDCBFFConfig.allow_unverified_id_token_for_custom_oidc=True (insecure unless "
                "your provider verifies id_token before returning it)."
            ),
        )
    return _subject_from_id_token_parse_only(id_token)


def _with_query(*, base: str, path: str, query: dict[str, str]) -> str:
    p = path if path.startswith("/") else f"/{path}"
    root = base.rstrip("/")
    full = f"{root}{p}"
    parsed = urlparse(full)
    merged = parsed._replace(query=urlencode(query))
    if parsed.scheme and parsed.netloc:
        return urlunparse(merged)
    return f"{full}?{urlencode(query)}"


def _subject_from_id_token_parse_only(id_token: str) -> str:
    """Parse ``sub`` from an OIDC ``id_token`` without signature verification."""
    try:
        parts = id_token.split(".")
        if len(parts) != 3:
            raise ValueError("not a JWT")
        payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
        raw = base64.urlsafe_b64decode(payload_b64.encode("ascii"))
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as e:
        raise HTTPException(status_code=502, detail="Invalid id_token") from e
    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub:
        raise HTTPException(status_code=502, detail="id_token missing sub")
    return sub


__all__ = [
    "GenericOIDCClient",
    "GenericOIDCClientConfig",
    "InMemoryOIDCBFFTokenStore",
    "OIDCBFFConfig",
    "OIDCBFFTokenStore",
    "OIDCProvider",
    "pkce_pair",
    "register_oidc_bff_routes",
]
