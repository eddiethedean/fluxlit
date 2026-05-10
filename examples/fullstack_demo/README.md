# Full-stack FluxLit demo

**SQLModel** + **SQLite** with the **`sqlite+rapsqlite`** dialect (true async I/O, same SQLAlchemy async session API you would use with `aiosqlite`). **Alembic** still runs against plain **`sqlite:`** on the **same database file** (sync `sqlite3` driver — the usual pattern so migrations stay simple).

Also includes **bcrypt** password hashes, **HS256 JWT** on login, protected API routes, and a **Streamlit** UI using `ApiClient` / `ApiClient.for_fluxlit`.

## Setup

From the **repository root**:

```bash
pip install -e '.[auth]'
pip install -r examples/fullstack_demo/requirements.txt
cd examples/fullstack_demo
alembic upgrade head
fluxlit dev app:app
```

Or install editable from the example directory:

```bash
cd examples/fullstack_demo
pip install -e '../../[auth]'
pip install -r requirements.txt
alembic upgrade head
fluxlit dev app:app
```

Open the URL printed by FluxLit (Streamlit + API on one port).

`rapsqlite` ships wheels for common platforms; building from source needs a Rust toolchain (see [rapsqlite docs](https://rapsqlite.readthedocs.io/en/latest/installation.html)).

## Security notes (demo vs production)

- **Passwords** are stored as **bcrypt** hashes only; login uses constant-time-friendly verification via passlib.
- **JWT** uses FluxLit’s `issue_hs256_access_token` and `JWTBearer`. For anything beyond local demos, set strong secrets and rotation:
  - `JWT_SECRET` (or prefer asymmetric JWKS and your IdP in production).
  - `JWT_ISSUER`, `JWT_AUDIENCE`, `JWT_TTL_SECONDS` as appropriate.
- **DATABASE_URL** defaults to `sqlite:///…/fullstack_demo.db` (sync form). The app derives **`sqlite+rapsqlite:///…`** for the async engine automatically.
- This example does not implement refresh tokens, MFA, or rate limiting; add those for real deployments.

## Layout

| Piece | Role |
| --- | --- |
| `models.py` | SQLModel `User` table |
| `database.py` | Async engine (rapsqlite) + `get_db` |
| `security.py` | bcrypt + JWT minting |
| `app.py` | `FluxLit` app: async register/login/`/users/me` + Streamlit UI |
| `alembic/` | Migrations (`users` table, sync sqlite on same file) |
