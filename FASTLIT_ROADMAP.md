
# FastLit — Development Roadmap

# Phase 0 — Foundation

## Goals
- establish architecture
- validate runtime strategy
- create developer experience baseline

## Deliverables
- repository structure
- pyproject.toml
- CI/CD
- linting
- typing
- testing framework
- docs structure

## Recommended Stack
- FastAPI
- Starlette
- Uvicorn
- Streamlit
- Pydantic Settings
- Typer
- AnyIO

---

# Phase 1 — Unified Runtime MVP

## Goals
- single CLI
- single exposed port
- unified startup/shutdown

## Features
- `fastlit dev`
- `fastlit run`
- managed subprocess orchestration
- reverse proxy layer
- API routing
- Streamlit routing
- internal service discovery

## Success Criteria
- developers can build full apps without configuring ports manually

---

# Phase 2 — Developer Experience

## Goals
- reduce boilerplate
- improve ergonomics

## Features
- app scaffolding
- automatic page discovery
- route decorators
- typed API client
- hot reload integration
- unified logging

## CLI
- `fastlit new`
- `fastlit build`
- `fastlit doctor`

---

# Phase 3 — Auth & Sessions

## Goals
- production-safe authentication

## Features
- JWT auth
- cookie sessions
- proxy-header auth
- OAuth integrations
- role-based access

## Enterprise Features
- CAC compatibility
- SSO integrations
- reverse proxy compatibility

---

# Phase 4 — Production Runtime

## Goals
- production readiness

## Features
- health checks
- metrics
- structured logging
- tracing
- Docker support
- Kubernetes manifests
- root_path handling
- graceful shutdown

---

# Phase 5 — Native ASGI Exploration

## Goals
- eliminate runtime fragmentation

## Research Areas
- direct Streamlit ASGI embedding
- websocket lifecycle unification
- shared event loop

## Potential Outcomes
- fully native ASGI runtime
- hybrid compatibility layer

---

# Phase 6 — Ecosystem Expansion

## Goals
- platform growth

## Features
- plugin architecture
- reusable UI components
- deployment adapters
- admin tooling
- realtime streaming
- background jobs

---

# Testing Strategy

## Required Coverage
- runtime orchestration
- websocket stability
- auth/session behavior
- proxy compatibility
- Streamlit page lifecycle

## CI Targets
- Linux
- macOS
- Windows

---

# Success Metrics

## Developer Experience
- minimal configuration
- fast startup
- stable hot reload

## Production
- reliable deployment
- proxy compatibility
- scalable architecture

## Community
- strong docs
- templates/examples
- plugin ecosystem
