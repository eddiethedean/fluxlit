
# FluxLit (`fluxlit`)

Production-grade unified runtime for FastAPI + Streamlit applications.

---

# Overview

FluxLit combines:
- FastAPI
- Streamlit
- authentication
- routing
- configuration
- deployment

into a single coherent application framework.

The goal is to make building Python-first production web applications dramatically simpler.

---

# Why FluxLit?

Combining FastAPI and Streamlit manually usually requires:
- multiple processes
- reverse proxies
- separate ports
- custom auth plumbing
- fragile deployment setups

FluxLit solves this with:
- one app object
- one CLI
- one deployment model
- one runtime experience

---

# Example

```python
from fluxlit import FluxLit

app = FluxLit(title="Admin Portal")

@app.api.get("/users")
def users():
    return [{"name": "Odos"}]

@app.page("/")
def home(st, client):
    st.title("Dashboard")
    st.write(client.get("/users").json())
```

Run:

```bash
fluxlit dev app:app
```

---

# Features

## Unified Runtime
- FastAPI + Streamlit together
- one exposed port
- managed orchestration

## Production Focused
- reverse proxy support
- Docker compatible
- Kubernetes compatible
- health checks
- structured logging

## Authentication
- JWT auth
- session auth
- proxy header auth
- OAuth integrations

## Developer Experience
- typed APIs
- page discovery
- hot reload
- app scaffolding

---

# Proposed Project Structure

```text
my_app/
├── app.py
├── pages/
├── api/
├── services/
├── static/
└── fluxlit.toml
```

---

# CLI

```bash
fluxlit new my-app
fluxlit dev app:app
fluxlit run app:app
```

---

# Architecture

Browser
↓
FluxLit Gateway
├── /api/* → FastAPI
├── /app/* → Streamlit
├── /auth/* → Auth/session
└── /static/* → Assets

---

# Roadmap

## Initial Release
- unified runtime
- CLI
- reverse proxy
- shared config

## Future
- native ASGI mode
- plugin system
- realtime support
- deployment adapters

---

# Philosophy

FluxLit aims to become the production runtime for Python-first web applications.

The framework prioritizes:
- simplicity
- strong typing
- operational stability
- enterprise deployment compatibility
- Python-native workflows

---

# Status

Alpha: unified dev server (`fluxlit dev`), ASGI gateway (`/api` → FastAPI, everything else → Streamlit), and scaffolding (`fluxlit new`).
