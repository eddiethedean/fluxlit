"""FluxLit full-stack demo: FastAPI + SQLite + Alembic + Streamlit + JWT.

The entry module is named ``main`` (not ``app``) so ``import app`` never resolves to
FluxLit's own ``fluxlit.app`` package when ``PYTHONPATH`` includes ``.../src/fluxlit``.

Run from this directory::

    pip install -e '../../[auth]'
    pip install -r requirements.txt
    alembic upgrade head
    export PYTHONPATH="$(pwd)"
    fluxlit dev
    # or explicitly: fluxlit dev main:app
"""

from __future__ import annotations

from typing import Annotated, Any

import httpx
from database import get_db
from fastapi import Depends, HTTPException, status
from models import User
from pydantic import BaseModel
from schemas import LoginRequest, RegisterRequest, TokenResponse, UserPublic
from security import (
    JWT_AUDIENCE,
    JWT_ISSUER,
    JWT_SECRET,
    JWT_TTL_SECONDS,
    hash_password,
    mint_access_token,
    verify_password,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from fluxlit import FluxLit
from fluxlit.auth.jwt import JWTAuthConfig, JWTBearer, StandardClaims
from fluxlit.client import ApiClient

_bearer = JWTBearer(
    JWTAuthConfig(
        issuer=JWT_ISSUER,
        audience=JWT_AUDIENCE,
        algorithms=["HS256"],
        hs256_secret=JWT_SECRET,
    )
)

app = FluxLit(title="FluxLit Full-Stack Demo")


class MeResponse(BaseModel):
    sub: str | None
    email: str | None = None
    full_name: str | None = None


@app.api.post("/auth/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],  # noqa: B008
) -> User:
    result = await db.execute(select(User).where(User.email == body.email.lower()))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(
        email=body.email.lower(),
        password_hash=hash_password(body.password),
        full_name=body.full_name.strip(),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@app.api.post("/auth/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],  # noqa: B008
) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == body.email.lower()))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        # Same message to avoid user enumeration.
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = mint_access_token(user_id=user.id, email=user.email, full_name=user.full_name)
    return TokenResponse(access_token=token, expires_in=JWT_TTL_SECONDS)


@app.api.get("/users/me", response_model=MeResponse)
async def users_me(
    claims: Annotated[StandardClaims, Depends(_bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],  # noqa: B008
) -> MeResponse:
    uid = int(claims.sub or "0")
    user = await db.get(User, uid)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    extra = claims.model_dump(mode="python")
    email = extra.get("email") if isinstance(extra.get("email"), str) else user.email
    full_name = extra.get("name") if isinstance(extra.get("name"), str) else user.full_name
    return MeResponse(sub=claims.sub, email=email, full_name=full_name)


@app.api.get("/health/db")
async def health_db(
    db: Annotated[AsyncSession, Depends(get_db)],  # noqa: B008
) -> dict[str, str]:
    await db.execute(text("SELECT 1"))
    return {"database": "ok"}


def _inject_modern_style(st: Any) -> None:
    st_mod = st
    st_mod.markdown(
        """
        <style>
            .block-container { padding-top: 2rem; max-width: 720px; }
            div[data-testid="stVerticalBlock"] > div:first-child h1 {
                font-family: system-ui, sans-serif;
                letter-spacing: -0.02em;
            }
            .demo-hero {
                padding: 1.25rem 1.5rem;
                border-radius: 12px;
                background: linear-gradient(135deg, #1e3a5f 0%, #0d2137 100%);
                color: #e8f1ff;
                margin-bottom: 1.5rem;
            }
            .demo-hero p { color: #b8d4f0; margin: 0.5rem 0 0 0; }
        </style>
        """,
        unsafe_allow_html=True,
    )


@app.page("/")
def home(st: Any, client: ApiClient) -> None:
    _inject_modern_style(st)
    if "access_token" not in st.session_state:
        st.session_state["access_token"] = None

    st.markdown(
        '<div class="demo-hero"><h1>FluxLit demo</h1>'
        "<p>FastAPI + SQLModel + SQLite (rapsqlite, async) · Alembic · JWT · Streamlit.</p></div>",
        unsafe_allow_html=True,
    )

    token = st.session_state.get("access_token")
    if token:
        with ApiClient.for_fluxlit(bearer_token=token) as api:
            try:
                me = api.get_model("/users/me", MeResponse)
            except httpx.HTTPStatusError as exc:
                st.session_state["access_token"] = None
                st.error(exc.response.text)
                st.rerun()
                return
        c1, c2 = st.columns(2)
        with c1:
            st.metric("Account", me.email or "—")
        with c2:
            st.metric("Name", me.full_name or "—")
        st.success("You are signed in. API calls use **ApiClient.for_fluxlit** with your JWT.")
        if st.button("Sign out", type="primary"):
            st.session_state["access_token"] = None
            st.rerun()
        return

    tab_reg, tab_log = st.tabs(["Create account", "Sign in"])
    with tab_reg:
        st.subheader("Register")
        with st.form("register"):
            email_r = st.text_input("Email", key="reg_email")
            name_r = st.text_input("Full name", key="reg_name")
            pw_r = st.text_input("Password (min 8 chars)", type="password", key="reg_pw")
            if st.form_submit_button("Register"):
                if not email_r or not name_r or not pw_r:
                    st.warning("Fill all fields.")
                else:
                    r = client.post(
                        "/auth/register",
                        json={"email": email_r, "full_name": name_r, "password": pw_r},
                    )
                    if r.status_code != 201:
                        st.error(r.json().get("detail", r.text))
                    else:
                        st.success("Account created. Use **Sign in**.")
    with tab_log:
        st.subheader("Sign in")
        with st.form("login"):
            email_l = st.text_input("Email", key="log_email")
            pw_l = st.text_input("Password", type="password", key="log_pw")
            if st.form_submit_button("Sign in"):
                if not email_l or not pw_l:
                    st.warning("Email and password required.")
                else:
                    r = client.post(
                        "/auth/login",
                        json={"email": email_l, "password": pw_l},
                    )
                    if r.status_code != 200:
                        st.error(r.json().get("detail", r.text))
                    else:
                        st.session_state["access_token"] = r.json()["access_token"]
                        st.rerun()
