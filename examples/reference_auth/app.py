"""Minimal FluxLit reference: FastAPI JWT + Streamlit ApiClient (dev HS256 only)."""

from __future__ import annotations

from typing import Annotated

import httpx
from fastapi import Depends
from pydantic import BaseModel

from fluxlit import FluxLit
from fluxlit.auth.jwt import JWTAuthConfig, JWTBearer, StandardClaims, issue_hs256_access_token
from fluxlit.client import ApiClient

# Development secret only — use JWKS + your IdP or vault-held secrets in production.
_SECRET = "reference-auth-dev-secret-32bytes-minimum-length-ok"
_ISSUER = "reference-auth"
_AUDIENCE = "reference-audience"

_bearer = JWTBearer(
    JWTAuthConfig(
        issuer=_ISSUER,
        audience=_AUDIENCE,
        algorithms=["HS256"],
        hs256_secret=_SECRET,
    )
)

app = FluxLit(title="Reference auth")


class DevLoginResponse(BaseModel):
    access_token: str
    token_type: str


class MeResponse(BaseModel):
    sub: str | None
    scope: str | None


@app.api.post("/dev/login")
def dev_login() -> DevLoginResponse:
    """Return a short-lived JWT for local demos (not for production)."""
    token = issue_hs256_access_token(
        subject="demo-user",
        issuer=_ISSUER,
        audience=_AUDIENCE,
        secret=_SECRET,
        ttl_seconds=3600,
        extra_claims={"scope": "read"},
    )
    return DevLoginResponse(access_token=token, token_type="bearer")


@app.api.get("/me")
def me(claims: Annotated[StandardClaims, Depends(_bearer)]) -> MeResponse:
    return MeResponse(sub=claims.sub, scope=claims.scope)


@app.page("/")
def home(st, client: ApiClient) -> None:
    st.title("Reference auth")
    if "access_token" not in st.session_state:
        st.session_state["access_token"] = None

    token = st.session_state["access_token"]
    if not token:
        st.caption("Injected `client` for login; `ApiClient.for_fluxlit` for authenticated calls.")
        if st.button("Sign in (dev)"):
            r = client.post("/dev/login")
            if r.status_code != 200:
                st.error(r.text)
                return
            parsed = DevLoginResponse.model_validate_json(r.content)
            st.session_state["access_token"] = parsed.access_token
            st.rerun()
        return

    with ApiClient.for_fluxlit(bearer_token=token) as api:
        try:
            me = api.get_model("/me", MeResponse)
        except httpx.HTTPStatusError as exc:
            st.error(exc.response.text)
            return
        st.write(me.model_dump())
