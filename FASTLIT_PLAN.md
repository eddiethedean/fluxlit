
# FastLit — Product & Architecture Plan

## Vision

FastLit is a production-grade Python application runtime that unifies FastAPI and Streamlit into a single coherent developer experience.

The goal is to eliminate the operational and architectural friction of combining:
- FastAPI APIs
- Streamlit UIs
- authentication
- routing
- deployment
- configuration
- sessions
- reverse proxy support
- production lifecycle management

FastLit should feel to Python developers like:
- Next.js feels to React developers
- Django feels to full-stack Python developers
- Rails feels to Ruby developers

while preserving the strengths of:
- FastAPI's API ecosystem
- Streamlit's rapid UI development workflow

---

# Core Product Principles

## 1. One App

Users should interact with:
- one app object
- one runtime
- one configuration model
- one deployment target

instead of manually orchestrating:
- separate processes
- ports
- proxies
- auth systems
- API URLs

---

## 2. Production First

FastLit is not a demo launcher.

The package must support:
- enterprise reverse proxies
- Kubernetes
- Docker
- Posit Workbench / Posit Connect
- authentication providers
- structured logging
- health checks
- scaling patterns
- secure deployments

---

## 3. Pythonic

The API should feel:
- declarative
- typed
- discoverable
- explicit where needed
- minimal boilerplate

---

# Proposed Architecture

## Runtime Layers

Browser
↓
FastLit Gateway
├── /api/* → FastAPI
├── /app/* → Streamlit
├── /auth/* → Auth/session
└── /static/* → Assets

---

## Initial Runtime Strategy

### Phase 1: Sidecar Runtime

Run:
- FastAPI
- Streamlit

as managed subprocesses behind:
- a unified ASGI gateway
- reverse proxy layer

Benefits:
- stable
- compatible with current Streamlit
- production-safe
- lower engineering risk

---

### Phase 2: Native ASGI Runtime

Investigate:
- direct Streamlit ASGI integration
- Starlette mounting
- unified event loops
- shared websocket handling

Goal:
single-process deployment.

---

# Core Modules

## fastlit.app
Unified application object.

## fastlit.api
FastAPI router integration helpers.

## fastlit.page
Streamlit page registration.

## fastlit.auth
Shared authentication/session layer.

## fastlit.client
Internal typed API client.

## fastlit.config
Configuration management.

## fastlit.runtime
Process orchestration/runtime lifecycle.

## fastlit.gateway
Unified proxy/routing layer.

## fastlit.deploy
Deployment tooling.

---

# Authentication Strategy

## Supported Modes

### Header-based enterprise auth
Examples:
- SSO
- CAC headers
- reverse proxy auth

### JWT auth

### Session-cookie auth

### OAuth providers
- Azure AD
- Okta
- Google
- GitHub

---

# Deployment Targets

## Officially Supported

- Docker
- Kubernetes
- Posit Workbench
- Posit Connect
- Linux VMs
- systemd
- uvicorn/hypercorn

---

# Technical Risks

## Streamlit internals
Streamlit is not fully designed as an embeddable ASGI app.

Mitigation:
- begin with sidecar model
- isolate Streamlit runtime
- abstract runtime boundary

---

## Websocket handling
Streamlit relies heavily on websocket behavior.

Mitigation:
- dedicated gateway abstraction
- websocket integration tests

---

# Long-Term Vision

FastLit becomes:
- the default production runtime for Python-first apps
- a serious alternative to lightweight JS frontend stacks
- a bridge between data science and application engineering

Potential future expansions:
- component system
- SSR/hybrid rendering
- typed frontend state
- native desktop runtime
- plugin ecosystem
- background jobs
- realtime streaming
