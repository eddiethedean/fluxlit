"""Minimal FluxLit reference: FastAPI JWT + Streamlit ApiClient (dev HS256 only)."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from fluxlit import FluxLit
from fluxlit.client import ApiClient
from fluxlit.jwt_auth import JWTAuthConfig, JWTBearer, StandardClaims, issue_hs256_access_token

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


@app.api.post("/dev/login")
def dev_login() -> dict[str, str]:
    """Return a short-lived JWT for local demos (not for production)."""
    token = issue_hs256_access_token(
        subject="demo-user",
        issuer=_ISSUER,
        audience=_AUDIENCE,
        secret=_SECRET,
        ttl_seconds=3600,
        extra_claims={"scope": "read"},
    )
    return {"access_token": token, "token_type": "bearer"}


@app.api.get("/me")
def me(claims: Annotated[StandardClaims, Depends(_bearer)]) -> dict[str, str | None]:
    return {"sub": claims.sub, "scope": claims.scope}


@app.page("/")
def home(st, client: ApiClient) -> None:
    st.title("Reference auth")
    _ = client  # default client is unauthenticated; use bearer below
    token = st.session_state.get("access_token")
    if not token:
        st.info("Get a token: `curl -s -X POST http://127.0.0.1:8000/api/dev/login`")
        entered = st.text_input("Paste access_token", type="password")
        if entered:
            st.session_state["access_token"] = entered
            st.rerun()
        return

    with ApiClient.for_fluxlit(bearer_token=token) as api:
        r = api.get("/me")
        if r.status_code != 200:
            st.error(r.text)
            return
        st.write(r.json())
