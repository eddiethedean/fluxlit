# FluxLit smoke app

This is the canonical tiny app used for release smoke checks, Playwright E2E,
Docker proxy validation, and local load scripts.

Run it from the repository root:

```bash
fluxlit run examples.smoke_app.app:app --no-pidfile
```

Expected public contract:

- `GET /api/healthz` returns `{"status": "ok"}`.
- `GET /api/smoke` returns a JSON object with marker `fluxlit_smoke_ok`.
- The Streamlit home page renders `FluxLit Smoke` and `fluxlit_smoke_ok`.
