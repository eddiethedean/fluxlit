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
export PYTHONPATH="$(pwd)"
fluxlit dev
```

Or install editable from the example directory:

```bash
cd examples/fullstack_demo
pip install -e '../../[auth]'
pip install -r requirements.txt
alembic upgrade head
export PYTHONPATH="$(pwd)"
fluxlit dev
```

**Why `main.py` and `fluxlit.toml`?** The FluxLit instance lives in **`main.py`** as **`app`**, and the default target is **`main:app`**.

Historically this example avoided `app.py` because a polluted `PYTHONPATH` could cause `import app` to resolve to FluxLit’s internal `app.py` instead of your project’s file. FluxLit now prefers `./app.py` when you run `fluxlit dev app:app` from the project directory, so the naming collision is no longer a problem.

Set **`PYTHONPATH`** to this directory so `main` resolves. **`fluxlit.toml`** sets `target = "main:app"` so you can run plain **`fluxlit dev`** from this folder. Open the **gateway** URL FluxLit prints (e.g. `http://127.0.0.1:8501`); Streamlit may use another ephemeral port internally.

**API docs:** Swagger is served at **`/api/docs`** (and ReDoc at **`/api/redoc`**). As of recent FluxLit versions, **`/docs`** at the gateway root redirects there so you are not sent to Streamlit (which used to look like a blank page).

`rapsqlite` ships wheels for common platforms; building from source needs a Rust toolchain (see [rapsqlite docs](https://rapsqlite.readthedocs.io/en/latest/installation.html)).

## Tests

From `examples/fullstack_demo` (after installing deps):

```bash
pip install -r requirements-test.txt
pytest
```

This example’s suite is self-contained (no `slow` / `e2e` markers). When working on **FluxLit itself** at the repo root, follow **[docs/testing.md](../../docs/testing.md)** (`-m "not slow"`, optional coverage, Playwright E2E).

Tests use FluxLit’s **`FluxLitTestClient`** (`fluxlit.testing`): HTTP goes through **`build_gateway`** with the real **`/api`** prefix (same as production), and **`openapi()`** / **`api_get("/healthz")`** match what the combined app exposes. **`streamlit()`** runs Streamlit’s **`AppTest`** against `fluxlit.streamlit_main` with `FLUXLIT_APP=main:app`.

Each test gets a temporary `sqlite+rapsqlite` file and a FastAPI **`get_db`** override so `fullstack_demo.db` is never used.

| File | Coverage |
| --- | --- |
| `tests/test_auth.py` | Register, login, `/users/me`, validation (422), JWT issuer/audience rejection, email normalization |
| `tests/test_gateway.py` | `/healthz`, OpenAPI shape |
| `tests/test_streamlit_home.py` | Home page renders in `AppTest` (Streamlit ≥ 1.30) |

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
| `main.py` | `FluxLit` instance `app`: async register/login/`/users/me` + Streamlit UI |
| `fluxlit.toml` | Default `target = "main:app"` for `fluxlit dev` |
| `alembic/` | Migrations (`users` table, sync sqlite on same file) |
| `tests/` | Pytest suite using `FluxLitTestClient` + `AppTest` |
