# Changelog

## Unreleased

<!-- Add user-facing bullets above before tagging; keep this section between releases. -->

## 0.13.0 - 2026-05-13

- **Phase 2 follow-through:** ``scripts/soak_metrics.sh`` and soak methodology in {doc}`runbooks` / {doc}`testing`; weekly **informational** FluxLit soak job in ``soak-scheduled.yml``; ``soak-fluxlit-dispatch`` runs metrics soak when metrics are enabled.
- **Scale docs:** multi-replica **Redis / shared store** failure modes in {doc}`url-session`; **ingress engine** pointer table in {doc}`deployment` and cross-link in {doc}`production-tls`.
- **Stability charter in code:** module notes on metrics/manifest/logs/settings; ``MANIFEST_V1_*`` key sets; contract tests for Prometheus series names vs ``GATEWAY_PROMETHEUS_METRICS`` and manifest v1 keys.
- **DX:** expanded ``fluxlit doctor --strict`` rows (OAuth subpath, proxy headers, upstream read timeout, rejected forward names, unlimited proxied body with ``trust_proxy``, CORS/security headers, conflicting public base URL envs); optional ``FLUXLIT_STRICT_STARTUP`` / ``strict_startup`` on :class:`~fluxlit.config.FluxlitSettings` to **raise** on the same class of misconfigurations at import time.
- **Tracing:** nested ``fluxlit.gateway.upstream_http`` span (hook) around the gateway → Streamlit **HTTP** hop; observability docs updated for span names and **W3C traceparent** passthrough on the internal hop.
- **Security / supply chain:** ``SECURITY.md`` supported-version policy aligned with the current **0.x** line and support matrix; **httpx** private typing imports called out with a contract test (``tests/test_httpx_import_contract.py``) and a contributor bump note in ``CONTRIBUTING.md``.
- **Pages:** ``Cookie`` resolves from ``set_page_cookie_context`` and ``st.context.cookies`` (same precedence pattern as ``Header``); ``fluxlit doctor`` hints mention explicit header/cookie injection when HTTP forwarding is off.
- **Ops:** ``GET /api/readyz`` Streamlit probe aggregates per-path HTTP statuses when every candidate URL is non-2xx (``upstream_http_failed`` detail with ``path:code`` segments).
- **Gateway:** access-log query redaction treats ``query_string`` decode failures as ``UnicodeError`` only (custom ``decode`` implementations used in tests).
- **Docs:** support matrix intro targets **0.13.x**; Streamlit pages typing documents ``Cookie`` resolution and async-``Depends`` timeout / daemon-thread caveat.

**Upgrading from 0.12.x:** Bump pins to ``fluxlit>=0.13,<1.0``. Optional: set ``FLUXLIT_STRICT_STARTUP=1`` in containers where misconfiguration should fail the process early; expand ``fluxlit doctor --strict`` in CI if you rely on the new FAIL rows.

## 0.12.0 - 2026-05-13

- **Stability charter:** documented gateway **Prometheus** metric names/labels/bucket policy, **page manifest** ``manifest_version`` 1 fields, structured log field contracts, and **experimental** ``FluxlitSettings`` flags in {doc}`support-matrix` and expanded {doc}`observability`; draft **1.0 compatibility & deprecation** subsection.
- **Multi-replica:** operations checklist in {doc}`deployment`; new runbook **Multi-replica: new Streamlit session after refresh**; optional Kubernetes **PDB** and **Service sessionAffinity** examples under ``examples/kubernetes/``; cross-links from {doc}`url-session`.
- **Evidence:** new ``scripts/soak_readyz.sh`` for ``/api/readyz`` soak summaries; chaos/soak script headers aligned with expected signals; {doc}`runbooks` scripted load table; manual **GitHub Actions** workflow ``soak-fluxlit-dispatch.yml``; {doc}`testing` recipe.
- **DX:** ``fluxlit doctor --strict`` treats broad ``forwarded_allow_ips`` (with ``trust_proxy``) and ``public_base_url`` path vs public mount mismatch as **FAIL** (use with ``--warnings-only`` or fix config).

**Upgrading from 0.11.x:** Bump pins to ``fluxlit>=0.12,<1.0``. CI or release gates may use ``fluxlit doctor --strict`` alongside ``fluxlit config --strict`` for proxy hardening. Re-read {doc}`support-matrix` stability tables when pinning dashboards or manifest consumers.

## 0.11.0 - 2026-05-12

- **Runtime:** unified ``FluxLit`` ASGI lifespan fails fast when Uvicorn runs with ``workers`` > 1 (detected via ``uvicorn.lifespan.on.LifespanOn``); set ``FLUXLIT_ALLOW_UNIFIED_UVICORN_MULTIWORKER=1`` to override (unsupported). See {doc}`deployment` and {doc}`configuration`.
- **Gateway:** log at **DEBUG** on ``fluxlit.gateway`` when Prometheus histogram observation raises instead of swallowing silently (the request still completes; that hop’s metric may be missing).
- **Roadmap:** Phase 2 “suggested PR slices” subsection links scripts, docs, and follow-up DX work.
- **Proxy matrix:** Traefik **v3.2** strip-prefix smoke stack on port **8085** (`docker-compose.traefik.yml`, `traefik-dynamic.yml`); wired into `docker/proxy-deployment/run-all-proxy-smokes.sh` and the reverse-proxy matrix in {doc}`deployment`.
- **Cookbook:** gateway Prometheus metrics, Kubernetes-style `healthz` / `readyz` probes, `fluxlit config --strict` in CI, and `FLUXLIT_GATEWAY_MAX_PROXY_REQUEST_BODY_BYTES` / **413** guidance in {doc}`cookbook`.
- **Diagnostics:** :func:`fluxlit.gateway.forward_headers.rejected_gateway_forward_header_allowlist` and settings capture of rejected allowlist names; `fluxlit config` / :func:`~fluxlit.config.config_print.collect_configuration_warnings` warn on credential-style names users listed but the gateway never forwards, and when `trust_proxy` is on with unlimited proxied upload body size; `fluxlit doctor` adds `gateway_forward_rejected_names`; verbose `gateway_proxy` includes `max_proxy_request_body_bytes` and `max_concurrent_upstream_http`.
- **Packaging:** Hatch sdist excludes stray virtualenv directories under ``examples/`` so ``uv build`` / PyPI sdists do not fail on disallowed symlinks.
- **Internal:** Consolidate affirmative ``FLUXLIT_*`` environment parsing via ``fluxlit.runtime.env_parse.truthy_env`` (used for ``FLUXLIT_DEBUG``, URL-session test guards, and related call sites).

**Upgrading from 0.10.x:** Bump pins to ``fluxlit>=0.11,<1.0``. Re-check ``FLUXLIT_GATEWAY_FORWARD_CLIENT_HEADERS_TO_STREAMLIT`` if you list credential header names (they are ignored); new warnings may appear in ``fluxlit doctor`` / ``fluxlit config --strict`` when ``trust_proxy`` is enabled without a body limit. If you run the unified ``FluxLit`` ASGI app under Uvicorn with ``--workers`` > 1, use **one worker per replica** and scale out (lifespan startup **fails** unless you set the unsupported ``FLUXLIT_ALLOW_UNIFIED_UVICORN_MULTIWORKER`` override).

## 0.10.0 - 2026-05-12

- **Gateway:** optional ``FLUXLIT_GATEWAY_FORWARD_CLIENT_HEADERS_TO_STREAMLIT`` / :attr:`~fluxlit.config.FluxlitSettings.gateway_forward_client_headers_to_streamlit` copies an allowlist of browser header names onto the gateway → Streamlit **HTTP** hop (``st.context.headers`` / :class:`~fluxlit.pages.di.Header`); credential and hop-by-hop names are rejected. See :mod:`fluxlit.gateway.forward_headers` and {doc}`configuration`.
- **Pages:** async :class:`~fluxlit.pages.di.Depends` callables and awaitable returns resolve when an asyncio loop is already running by using a short-lived side thread (0.9 raised ``TypeError`` in that case). :class:`~fluxlit.pages.di.Header` falls back to ``st.context.headers`` after ``set_page_header_context``.
- **Doctor / verbose:** new checks for readiness path hints, WebSocket proxy documentation pointers, upstream timeout sanity, async-depends warning, forwarded-header warning; ``gateway_proxy`` block in ``fluxlit doctor --verbose`` / ``--json``.
- **Proxy matrix:** Caddy strip-prefix smoke on port **8084** (``docker-compose.caddy.yml``); ``run-all-proxy-smokes.sh`` runs it; {doc}`deployment` compatibility table updated.
- **Docs:** new {doc}`cookbook` (recipes); expanded {doc}`streamlit-pages-typing` for async deps and header forwarding.

**Upgrading from 0.9.x:** Bump pins to ``fluxlit>=0.10,<1.0``. If you use ``FLUXLIT_ASYNC_PAGE_DEPENDS=1`` under asyncio-heavy hosts, re-test async ``Depends`` (resolution now uses a side thread when a loop is active). Optional header forwarding is off by default.

## 0.9.0 - 2026-05-12

- **Streamlit pages (0.9):** :class:`~fluxlit.pages.records.PageRecord` registry with :attr:`~fluxlit.app.FluxLit.page_records`; :meth:`~fluxlit.app.FluxLit.page` accepts ``icon``, ``tags``, and static ``page_meta``; handlers may return :class:`~fluxlit.pages.meta.PageMeta` for breadcrumbs and similar post-run UI. :class:`~fluxlit.pages.di.Depends`, :class:`~fluxlit.pages.di.Header`, and :class:`~fluxlit.pages.di.Cookie` resolve extra parameters beside ``(st, client)`` (see {doc}`streamlit-pages-typing`). Optional :class:`~fluxlit.url_session.SessionStore` on :class:`~fluxlit.app.FluxLit` enables ``SessionStore`` injection.
- **Navigation:** :meth:`~fluxlit.app.FluxLit.navigation` with :class:`~fluxlit.pages.navigation.NavigationModel` orders multipage sidebar entries by path.
- **Query / session:** :func:`~fluxlit.pages.query.parse_query_params`, :class:`~fluxlit.pages.query.Query`, :class:`~fluxlit.pages.session_state.SessionModel`, and :func:`~fluxlit.url_session.hydrate_url_session_typed` for typed URL/session payloads.
- **Registration & CI:** duplicate ``@app.page`` paths, or distinct paths that normalize to the same Streamlit ``url_path`` slug (for example ``/a`` and ``/a/``), raise ``ValueError`` at registration; :func:`~fluxlit.pages.validate.validate_fluxlit_pages` reports the same for CI.
- **Slug & lazy validate:** :func:`~fluxlit.pages.slug.page_slug` centralizes slug rules; ``validate_fluxlit_pages`` is available on :mod:`fluxlit.pages` via lazy ``__getattr__`` to avoid import cycles.
- **Manifest & CLI:** :meth:`~fluxlit.app.FluxLit.build_page_manifest` (``manifest_version`` **1**, ``manifest_stability`` **stable``); ``fluxlit pages manifest`` and ``fluxlit pages validate`` (``--strict`` for signature checks independent of settings); optional ``children`` keys from ``page_meta`` in the manifest.
- **PageMeta children & nav:** ``PageMeta.children`` merges title/icon overrides and sibling ordering before ``st.navigation`` (unknown paths warn); **cycles** in ``children`` emit ``UserWarning`` during ordering; :mod:`fluxlit.streamlit.nav_build` uses a heap-ordered frontier for the ready queue.
- **Deep links:** the Streamlit entrypoint passes the same ordered ``page_records`` list to :func:`~fluxlit.deep_links.match_nav_page` as to ``st.navigation``, so ``?page=`` matches the visible sidebar (see {doc}`deep-links`).
- **Strict signatures:** :class:`~fluxlit.config.FluxlitSettings.strict_page_signatures` / ``FLUXLIT_STRICT_PAGE_SIGNATURES``; clearer errors when annotations cannot be resolved.
- **Async depends:** optional async dependency callables when ``FLUXLIT_ASYNC_PAGE_DEPENDS=1`` (resolved with ``anyio.run`` when no asyncio loop is running); :attr:`~fluxlit.config.FluxlitSettings.async_page_depends` for ``fluxlit config`` / doctor visibility.
- **Experimental generator pages:** :class:`~fluxlit.pages.flags.FluxlitFeatureFlags` and :attr:`~fluxlit.config.FluxlitSettings.experimental_yield_pages` mirror ``FLUXLIT_EXPERIMENTAL_YIELD_PAGES``; when enabled, generator handlers run **two** ``next()`` steps in one script run. ``fluxlit doctor --check-pages`` / ``--verbose`` run validate-style checks and warn when this flag is on.
- **Docs:** PageMeta vs ``set_page_config`` truth table; gateway ``Header`` / ``Cookie`` bridge; generator and Protocol typing guidance; ``page_overrides`` / ``FLUXLIT_TEST_PAGE_OVERRIDES`` in {doc}`testing`; :mod:`fluxlit.gateway.http_proxy` notes on headers in the Streamlit process.
- **Tooling:** ``ty`` test overrides ignore ``invalid-parameter-default`` and ``unresolved-reference`` (FastAPI-style ``Depends`` defaults and deliberate forward refs in tests).
- **Testing:** :meth:`~fluxlit.testing.FluxLitTestClient.streamlit` accepts ``page_overrides`` (JSON via ``FLUXLIT_TEST_PAGE_OVERRIDES``) for dependency injection in AppTest.
- **Typing:** :class:`~fluxlit.app.FluxLit` is a :class:`typing.Generic` over settings type for static checkers; :class:`~fluxlit.streamlit.page.PageFn` allows optional :class:`~fluxlit.pages.meta.PageMeta` returns.
- **CLI / packaging:** ``fluxlit pages`` subgroup; ``fluxlit build`` Dockerfile pin ``fluxlit>=0.9,<1.0``; ``fluxlit new`` minimal scaffold includes ``typing.Any``, :class:`~fluxlit.client.ApiClient`, and a ``Depends`` example.

**Upgrading from 0.8.x:** Bump pins to ``fluxlit>=0.9,<1.0``. :attr:`~fluxlit.app.FluxLit.pages` remains ``(path, title, handler)`` tuples. Opt into ``strict_page_signatures``, manifest, and DI markers as needed; see {doc}`streamlit-pages-typing`.

## 0.8.1 - 2026-05-12

- **Gateway / settings:** ``normalize_api_mount_path`` in ``fluxlit.api_mount`` aligns gateway dispatch with ``internal_api_base_url`` and ``FluxLitPublicUrls`` when ``api_mount_path`` / ``FLUXLIT_API_MOUNT_PATH`` omits a leading slash (e.g. ``api`` → ``/api``); :class:`~fluxlit.config.FluxlitSettings` validates ``api_mount_path``; ``create_gateway_app`` normalizes ``FLUXLIT_API_PREFIX`` the same way.
- **Gateway:** WebSocket upstream ``websockets.connect`` **timeouts** (``TimeoutError``) are caught and the client socket is closed with code **1011** instead of leaking an ASGI exception.
- **Gateway:** Prometheus and debug JSON ASGI responses set ``more_body: false`` on the terminal body message (stricter ASGI consumers).
- **Client:** :class:`~fluxlit.client.ApiClient` rejects absolute and scheme-relative ``path`` values so httpx cannot bypass ``base_url`` to another host (:class:`ValueError`).
- **OIDC BFF:** :class:`~fluxlit.auth.oidc.OIDCBFFConfig` adds ``allow_unverified_id_token_for_custom_oidc`` (default ``False``). Non-:class:`~fluxlit.auth.oidc.GenericOIDCClient` providers must set it to ``True`` to keep parse-only ``id_token`` ``sub`` extraction (tests or providers that verify tokens themselves). Empty ``public_base_url`` now emits a **runtime warning** at route registration.
- **Docs / observability:** HTTP gateway proxy module and ``gateway_max_proxy_request_body_bytes`` document full upstream **response** buffering; :class:`~fluxlit.url_session.InMemorySessionStore` documents ``ttl_seconds=0`` semantics and trims oversize stores by **oldest insertion** order.
- **Docs:** README coverage wording matches CI (100% line coverage; one test-helper ``pragma: no cover``); historical CHANGELOG CI note uses ``--cov-fail-under=100``; ``docs/testing.md`` documents ``ty-check`` as a required workflow job; ``docs/security.md`` and ``docs/migration-auth.md`` cover the above auth/client changes.
- **CI:** ``ty-check`` no longer uses ``continue-on-error``.

**Upgrading from 0.8.0:** Bump pins (for example ``fluxlit==0.8.1`` in Compose lockfiles). If you use **custom** :class:`~fluxlit.auth.oidc.OIDCProvider` with :func:`~fluxlit.auth.oidc.register_oidc_bff_routes` (not :class:`~fluxlit.auth.oidc.GenericOIDCClient`), set ``OIDCBFFConfig.allow_unverified_id_token_for_custom_oidc=True`` **only** when your provider already verified ``id_token`` or in controlled tests; otherwise switch to ``GenericOIDCClient`` for JWKS validation. If :class:`~fluxlit.client.ApiClient` calls used absolute URLs as paths, switch to relative paths (or construct a separate httpx client for off-host calls).

## 0.8.0 - 2026-05-12

- **CLI:** `fluxlit config` prints resolved binding, redacted effective settings, derived internal API base, and structured configuration warnings (with documentation links); supports `--json` and `--strict`.
- **Public URLs:** `FluxLit.urls` exposes :class:`~fluxlit.application.public_urls.FluxLitPublicUrls` with `app_base`, `api_base`, `docs_url`, `redoc_url`, `openapi_url`, `health_url`, `ready_url`, and `for_page` (including `query=`) so links match `FLUXLIT_ROOT_PATH`, `FLUXLIT_API_MOUNT_PATH`, and `FLUXLIT_PUBLIC_BASE_URL` under the unified gateway.
- **Debug mode:** ``FLUXLIT_DEBUG=1`` or ``fluxlit dev`` / ``run`` / ``workbench`` with ``--debug`` turns on gateway access logs, API request logging, bumps the default log level to ``debug`` when it was still ``info``, serves a redacted ``GET /__fluxlit/debug`` snapshot (unless ``api_mount_path`` would shadow it), records recent dispatches in-process, prints a ``[fluxlit-debug]`` banner to stderr at unified startup, and makes :meth:`fluxlit.app.FluxLit.get_client` propagate ``X-Request-ID`` to the API. See ``docs/configuration.md``, ``docs/cli.md``, ``docs/troubleshooting.md``, and ``docs/observability.md``.
- **Doctor:** ``fluxlit doctor --verbose`` / ``-v`` prints a redacted effective-configuration snapshot (pages, derived internal API base, OpenAPI URLs, proxy/session extras); ``--json --verbose`` adds a ``verbose`` object to the payload.
- **Workbench / Posit:** ``fluxlit workbench`` and ``--workbench`` on ``dev`` / ``run`` enable Uvicorn proxy headers and print a loopback browser URL hint; see platforms and CLI docs for Posit Connect / Workbench-style ``FLUXLIT_ROOT_PATH`` deployments.
- **Testing, deep links, and multipage Streamlit:** ``FluxLitTestClient`` supports ``root_mount`` / ``with_root_path``, per-call ``root_path`` on ``api_get`` / ``api_post``, ``streamlit(..., query_params=...)``, and ``assert_docs_available()``; AppTest helpers ``apptest_assert_no_errors``, ``apptest_select_page``, and ``assert_no_streamlit_exception``; ``query_params``, ``match_nav_page``, and ``FluxLitPublicUrls.page_url`` for query and page URLs. The Streamlit entrypoint applies ``match_nav_page`` before ``st.navigation`` when using multipage ``nav_pages`` so ``?page=`` deep links resolve. See ``docs/testing.md`` and ``docs/deep-links.md``. Closes #31.
- **Streamlit → API client:** `ApiClient.with_bearer` for bearer auth on top of the injected page client; new guide `docs/streamlit-api-client.md` (when to use injected `client` vs `for_fluxlit`, errors, shared internal base). Closes #28.
- **Docs:** New guide {doc}`url-session-token-security` on URL-session ids vs auth tokens, email/invite links, JWTs in URLs, Referrer-Policy, and how logging/debug redaction applies. Cross-links from url-session, deep-links, secrets, security, and index. Closes #30.
- **Docs / proxy smoke:** Path-prefixed reverse-proxy guide for **`/apps/my-app`** in {doc}`production-tls`; Docker Compose + nginx under **`docker/proxy-deployment/`** (including CI **`run-all-proxy-smokes.sh`**); **`smoke-test.sh`** now asserts **`/api/docs`**. Closes #33.
- **Docs:** Expanded support matrix with production pinning patterns (`uv`, `pip-tools`), explicit core dependency lower bounds, Streamlit extra guidance, testing compatibility notes, and upgrade checklist cross-links.

**Upgrading from 0.7.x:** `fluxlit build` emits `pip install "fluxlit>=0.8,<0.9"` in generated Dockerfiles; refresh pinned Compose lockfiles (`examples/docker_compose/requirements.in` / `requirements.txt`) and Kubernetes image tags when you bump the FluxLit line. Run `fluxlit config` after changing proxy or public URL env vars.

## 0.7.0 - 2026-05-11

- **Testing API:** `streamlit_main_path()` is now a public helper for supported `AppTest.from_file(...)` usage; `FluxLitTestClient.streamlit()` uses it and sets `FLUXLIT_TESTS=1` during AppTest runs.
- **Testing docs:** `docs/testing.md` now includes an app-developer Pytest recipe, guidance for `FluxLitTestClient`, Streamlit `AppTest`, `ApiClient`, `st.data_editor`, dynamic widget keys, and multipage smoke tests. A new `examples/multipage_apptest/` demo shows stable multipage patterns.
- **URL session test mode:** URL-session helpers no-op under `FLUXLIT_TESTS=1` unless `FLUXLIT_FORCE_URL_SESSION_IN_TESTS=1` is set. `FLUXLIT_DISABLE_URL_SESSION=1` remains an explicit disable switch in any environment.
- **Doctor diagnostics:** `fluxlit doctor` reports additional import/config context, including `sys.path` head entries, ambiguous top-level import candidates, loaded module file paths, effective API prefix, URL-session state, proxy/public-base-url fields, and missing `auth` / `metrics` extras.
- **Configuration:** `FLUXLIT_PUBLIC_BASE_URL` is the preferred public OAuth base URL. `PUBLIC_BASE_URL` is accepted as a compatibility fallback only when the namespaced value is unset; `fluxlit doctor` warns or fails on conflicting values depending on `FLUXLIT_STRICT_PUBLIC_BASE_URL`.
- **Docs:** README, CLI, configuration, troubleshooting, URL-session, quickstart, testing, and roadmap docs were refreshed for the 0.7 testing and diagnostics work.

**Upgrading from 0.6.1:** Prefer `FLUXLIT_PUBLIC_BASE_URL` over `PUBLIC_BASE_URL` in deployment configuration. If your AppTest suite intentionally exercises URL-session continuity, set `FLUXLIT_FORCE_URL_SESSION_IN_TESTS=1`; otherwise `FLUXLIT_TESTS=1` now keeps URL-session helpers inert during headless tests.

## 0.6.1 - 2026-05-11

- **Runtime:** File-backed import targets now prepend the target module's directory to `sys.path` before execution, so top-level multi-file apps can use sibling imports with `main:app` and explicit `./path/main.py:app` targets without setting `PYTHONPATH`.

**Upgrading from 0.6.0:** Remove entrypoint workarounds that manually insert the app
directory into `sys.path` solely for sibling imports. Keep explicit package installs or
project-root test setup if your app intentionally imports packages outside the target
module's directory.

## 0.6.0 - 2026-05-11

- **0.6 development:** canonical smoke app shared by E2E/proxy/load paths; expanded `fluxlit doctor` diagnostics including `--json`; stable gateway log and Prometheus metric contracts; optional no-dependency tracing hooks plus an OpenTelemetry example; runnable URL-session external-store examples and platform docs; scaffold profiles; richer local smoke/load/chaos scripts; broader Docker proxy smoke matrix.

## 0.5.0 - 2026-05-11

- **Tests / CI:** coverage job enforces **`--cov-fail-under=100`**; **`ty-check`** job (pinned ``ty``); E2E uploads **Playwright traces** on failure; weekly **`soak-scheduled`** workflow exercises `scripts/soak_http.sh` against `http.server`; shared fixtures **`gateway_test_client_factory`** / **`requires_streamlit_apptest`**; gateway header-filter, Prometheus counter, readiness (`302` / `readyz` 404), WebSocket **`slow`** reconnect stress, and **`DictSessionStore`** contract tests.
- **URL session (Phase 2 follow-on):** `fluxlit.url_session` (`SessionStore`, `InMemorySessionStore`, `ensure_url_session`, `hydrate_url_session`, `persist_url_session`) for refresh continuity **without cookies**; user guide **`docs/url-session.md`**; AppTest + unit tests.
- **Gateway logs:** structured `query` field on gateway access / debug logs with **redacted** session query values (`fluxlit_sid` and `FLUXLIT_URL_SESSION_QUERY_PARAM`); new `FluxlitSettings.url_session_query_param`.
- **Kubernetes:** `examples/kubernetes/ingress.example.yaml` reference Ingress (not applied by default).
- **Supply chain & containers:** CI uploads a **CycloneDX** SBOM (`cyclonedx-sbom` artifact) alongside **`pip-audit`** on `.[auth]`; `fluxlit build`, `examples/docker_compose`, and `docker/proxy-deployment` use **digest-pinned** Python slim and **non-root** `appuser`; Compose example adds **`requirements.in` / `requirements.txt`** via **`pip-compile`**.
- **Docs:** **`docs/production-tls.md`** (TLS, HSTS, `forwarded_allow_ips`, CSP notes), **`docs/secrets.md`** (logs, secret stores, JWT/OIDC rotation); cross-links from README, index, deployment, configuration, security, observability, auth-recipes, troubleshooting, architecture, quickstart, testing, CONTRIBUTING, example READMEs, and **`ROADMAP.md`** security row status.
- **0.5 roadmap / production hardening:** **`examples/kubernetes/`** reference manifests; deployment scaling + multi-worker docs; **`docs/runbooks.md`**; **`docs/support-matrix.md`**; **`scripts/soak_http.sh`**; **`upgrade-smoke`** workflow; OpenAPI **contract** test; optional gateway **Prometheus** metrics (`fluxlit[metrics]`); observability updates (RED metrics, traceparent recipe, correlation limits).
- **Configuration:** `FluxlitSettings` / `FluxLit` passthroughs for Streamlit (`streamlit_run_cli_args`, `streamlit_page_config` → `st.set_page_config`) and Starlette `CORSMiddleware` (`cors_middleware_kwargs`); `fastapi_kwargs` documented as the full `FastAPI(...)` hook.
- **Gateway / operations:** authoritative `X-Request-ID` on proxied HTTP and WebSocket to Streamlit; `FluxlitSettings` for upstream connect/read timeouts, max proxied request body (**413**), concurrent upstream HTTP cap, shared `httpx.AsyncClient` connection limits, WebSocket open/ping/close/`max_size` tuning; `uvicorn_graceful_shutdown_timeout_s` wired into `fluxlit dev` / `fluxlit run` Uvicorn config when set.
- **Logging:** `fluxlit.logging.JsonLogFormatter` (stdlib JSON, merges `extra` fields).
- **Docs:** `docs/observability.md` (correlation diagram, JSON `dictConfig`, SLO/alerting sketches), `docs/deployment.md` (Kubernetes graceful shutdown), `docs/configuration.md` gateway env table; README, index, quickstart, architecture, testing cross-links.
- **Tests:** gateway correlation integration and proxy robustness modules; expanded `test_logging_json` / `test_config_settings`; `test_streamlit_page_config`; FastAPI `openapi_url` / CORS `expose_headers` coverage; unified lifespan asserting Streamlit argv includes `streamlit_run_cli_args`.
- **Safety:** Reject `streamlit_run_cli_args` that override sidecar port/address/baseUrlPath; strip CORS middleware kwargs that duplicate FluxLit-controlled keys; always set FastAPI `title` / `root_path` from settings after `fastapi_kwargs` merge.
- **ASGI / Uvicorn:** `FluxLit` is a first-class ASGI app (`uvicorn app:app`); unified stack via `asgi_from_fluxlit` / `create_unified_app` with lifespan bridged to the inner FastAPI app, Streamlit sidecar lifecycle, and spec-shaped HTTP/WebSocket error responses.
- **Imports:** `load_fluxlit` prefers a local `./<module>.py` when resolving targets (avoids `app.py` / `PYTHONPATH` shadowing); optional `FluxLit(import_target=...)` for explicit `module:attr`.
- **CLI:** `fluxlit new` writes `fluxlit.toml` with `target` and `gateway_port`; mentions `uvicorn app:app`.
- **Tests:** `tests/test_asgi_unified.py` for lifespan, concurrent HTTP, streaming request bodies, sidecar failure, and related edge cases.
- **Docs / roadmap:** Quickstart and deployment document the simple Uvicorn entrypoint; **ROADMAP** adds planned **Version 0.5** production-hardening themes and ties **Phase 4** delivery to that track.

## 0.4.1

- **Docs:** Fix PyPI version badge image URL in `README.md` (use Shields `pypi/v` badge).

## 0.4.0

- **Runtime (Windows):** ``fluxlit shutdown`` / ``shutdown_unified_process`` use ``taskkill /T`` instead of ``os.kill(SIGTERM)``; ``--force`` uses ``taskkill /T /F``. PID liveness uses ``OpenProcess`` (avoids locale-dependent ``tasklist`` parsing).
- **Readiness:** ``GET /api/readyz`` / ``fluxlit.health.probe_streamlit_ready`` require a **2xx** response from the Streamlit upstream root (stricter than treating any status below 500 as ready).
- **Gateway:** Return **502** when the Streamlit upstream URL resolves empty at request time (e.g. missing state file); WebSocket connections get a clear close when upstream is missing.
- **Dev:** On ``--reload-scope=full``, if the new Streamlit process does not open its port in time, terminate it, print stderr guidance, and stop the gateway.
- **CI:** Docs job runs ``sphinx-build -W`` (warnings as errors).
- **Docs:** Windows ``shutdown`` behavior (``taskkill``); deployment, observability, and troubleshooting updates for readiness behavior.
- **Runtime:** Map IPv6 unspecified bind ``::`` to loopback for ``FLUXLIT_INTERNAL_API_BASE`` (same as ``0.0.0.0``).
- **OIDC BFF:** Validate ``id_token`` with IdP JWKS when using ``GenericOIDCClient``; optional ``OIDCBFFConfig.id_token_audience`` / ``id_token_leeway_seconds``; parse-only fallback for other ``OIDCProvider`` stubs.
- **JWT:** Run PyJWT/JWKS decode in a worker thread via ``anyio.to_thread`` to avoid blocking the event loop.
- **Gateway:** Use Latin-1 for stripped ``raw_path``; log exceptions while streaming proxied response bodies.
- **API:** ``FluxLit.attach_oidc_login`` raises if called twice on the same instance.
- **CI:** Release workflow runs ``pip-audit`` (same as main CI); ``slow`` pytest marker; ``slow-tests`` and ``coverage`` jobs (upload ``coverage.xml`` artifact); expanded gateway and auth tests; Playwright E2E including ``FLUXLIT_ROOT_PATH``.
- **Docs:** OIDC in-memory store and JWKS ``id_token`` behavior in security, auth-recipes, and ``SECURITY.md``; fix OIDC docstring cross-reference (Streamlit exchange helpers); README, ``docs/testing.md``, index, roadmap testing table, and cross-links for the test/CI layout.

## 0.3.0

- **Auth (optional `fluxlit[auth]`):** JWT bearer validation with HS256 (dev) or JWKS (RS256/ES256), `RequireScopes` / `RequireRoles`, first-party HS256 minting for BFF flows.
- **OIDC:** `GenericOIDCClient` (OpenID discovery + Authorization Code with PKCE), `register_oidc_bff_routes` with one-time `auth_code` exchange for Streamlit-safe token handoff.
- **Forward auth:** `TrustedProxyUser` / `TrustedProxyUserConfig` with optional HTTPS and client-host checks.
- **Client:** `ApiClient` `default_headers`, `auth_header_factory`, `propagate_request_id`, and `ApiClient.for_fluxlit(bearer_token=...)`.
- **Streamlit:** `exchange_auth_code_from_query`, `bearer_headers_from_session`, `prepare_streamlit_api_client`.
- **Security:** opt-in `FluxlitSettings.enable_security_headers` and CORS (`cors_allow_origins`, `cors_allow_credentials`); `public_base_url` for OAuth redirects; `SECURITY.md` and CI `pip-audit` on `.[auth]`; PyPI `Security` project URL; sdist includes `SECURITY.md`.
- **CLI:** `fluxlit doctor` JWT clock-skew note, OAuth/CORS guidance.
- **Config / UX:** `FLUXLIT_JWT_*`, `FLUXLIT_OIDC_BFF_SECRET`, `jwt_leeway_seconds`; `JWTBearer.from_fluxlit_settings`, `FluxLit.make_jwt_bearer`, `FluxLit.attach_oidc_login`.
- **Docs:** security architecture, auth recipes, migration guide, README quick links and secured-API section, quickstart/index updates; reference example `examples/reference_auth/`; docs extra includes `itsdangerous` for Sphinx.
- **Tests:** JWT/OIDC/BFF/error-path coverage, Streamlit auth helpers, security middleware, `ApiClient` header merging / request-id propagation, friendly security ergonomics tests.

## 0.2.0

- **Config:** `fluxlit.toml` and `pyproject.toml` `[tool.fluxlit]` for default `target`, bind options, and log level (`fluxlit.config.project`). Precedence: CLI → environment → project file → defaults.
- **CLI:** `fluxlit build` writes a starter `Dockerfile` and `.dockerignore`; `fluxlit doctor` reports PASS/WARN/FAIL checks (import, port bind, deps, `FLUXLIT_INTERNAL_API_BASE`) with optional `--warnings-only`.
- **CLI:** `fluxlit dev` / `run` accept an omitted `target` when configured in a project file; `--reload-scope=gateway` documents gateway-only reload; stderr warns that Streamlit does not reload.
- **Pages:** `FluxLit.discover_pages(directory, package=...)` imports sibling modules and calls `register(app)` for opt-in multipage packages.
- **Client:** `ApiClient.get_model` / `post_model` for Pydantic-validated JSON.
- **Observability:** Gateway sets a request id from `X-Request-ID` (or generates one) via `logging_context`; optional `FluxlitSettings.enable_request_logging` adds FastAPI access logs at INFO.
- **Dependencies:** `tomli` on Python 3.10 for TOML parsing (stdlib `tomllib` on 3.11+).
- **Docs:** Sphinx + MyST site under `docs/`, optional `pip install -e ".[docs]"`, Read the Docs config (`.readthedocs.yaml`), CI `docs` job, PyPI `Documentation` URL points to RTD; repository planning docs live at `PLAN.md` and `ROADMAP.md`.
- **Testing:** Broader unit and integration tests (gateway edge cases, CLI, `streamlit_main` import paths, `pytest-cov` + Coverage config for the `src/` layout).

## 0.1.0

- Unified gateway + sidecar runtime (single public port; HTTP + WebSocket proxy to Streamlit).
- CLI: `dev`, `run`, `new`, `doctor`.
- Configurable API prefix (`api_mount_path` / gateway `api_prefix`) with `/api` default.
- Runtime hardening (gateway stops if Streamlit exits; improved shutdown behavior).
- Testing support:
  - FluxLit-native `FluxLitTestClient`
  - FastAPI/Starlette TestClient tests for gateway routing
  - Streamlit AppTest coverage (version-dependent)
  - CLI + ApiClient contract tests
- CI (GitHub Actions) and contributor docs.

