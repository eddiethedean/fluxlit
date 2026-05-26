"""Test helpers: gateway-scoped HTTP client and Streamlit ``AppTest`` integration."""

from __future__ import annotations

import contextlib
import json
import os
from collections.abc import Iterator
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import httpx
from starlette.testclient import TestClient

from fluxlit.api_mount import normalize_api_mount_path
from fluxlit.app import FluxLit
from fluxlit.gateway import build_gateway
from fluxlit.gateway.paths import normalize_root_mount


def streamlit_main_path() -> Path:
    """Return FluxLit's supported Streamlit entry script for ``AppTest.from_file``.

    Use this instead of constructing a path from ``fluxlit.__file__``; the helper is
    part of FluxLit's testing API and can keep working if the internal package layout
    changes.
    """
    return Path(__file__).resolve().parent / "streamlit" / "main.py"


def apptest_assert_no_errors(at: Any) -> None:
    """Raise :class:`AssertionError` if ``AppTest`` captured ``st.exception`` or ``st.error``.

    Use after :meth:`FluxLitTestClient.streamlit` (or any ``AppTest`` run) to fail fast
    when the script surfaced an error to users.
    """
    exc = getattr(at, "exception", None)
    if exc is not None and len(exc) > 0:
        details = [getattr(x, "value", repr(x)) for x in exc]
        msg = f"AppTest captured st.exception: {details!r}"
        raise AssertionError(msg)
    err = getattr(at, "error", None)
    if err is not None and len(err) > 0:
        details = [getattr(x, "value", repr(x)) for x in err]
        msg = f"AppTest captured st.error: {details!r}"
        raise AssertionError(msg)


def assert_no_streamlit_exception(at: Any) -> None:
    """Alias for :func:`apptest_assert_no_errors` (Streamlit ``AppTest`` naming)."""
    apptest_assert_no_errors(at)


def _streamlit_apptest_env(
    client: FluxLitTestClient,
    *,
    target: str,
    internal_api_base: str | None,
    page_overrides: dict[str, Any] | None,
) -> dict[str, str]:
    internal = internal_api_base or f"http://127.0.0.1:1{client._normalized_api_prefix()}"
    env: dict[str, str] = {
        "FLUXLIT_APP": target,
        "FLUXLIT_INTERNAL_API_BASE": internal,
        "FLUXLIT_API_PREFIX": normalize_api_mount_path(client.api_prefix),
        "FLUXLIT_TESTS": "1",
    }
    if page_overrides is not None:
        env["FLUXLIT_TEST_PAGE_OVERRIDES"] = json.dumps(page_overrides)
    return env


def apptest_select_page(
    at: Any,
    client: FluxLitTestClient,
    *,
    target: str,
    page: str,
    internal_api_base: str | None = None,
    extra_sys_path: str | Path | None = None,
    page_key: str = "page",
    page_overrides: dict[str, Any] | None = None,
) -> Any:
    """Set ``page`` query key and ``run()`` with the same ``FLUXLIT_*`` patch as ``streamlit``.

    ``AppTest.run`` does not automatically keep ``FLUXLIT_*`` variables from the first
    :meth:`FluxLitTestClient.streamlit` call; this helper re-applies the same patch
    :meth:`FluxLitTestClient.streamlit` uses so the entrypoint can resolve ``target``
    again after you change ``at.query_params``.
    """
    _import_streamlit()
    at.query_params[page_key] = page
    with (
        _patched_env(
            _streamlit_apptest_env(
                client,
                target=target,
                internal_api_base=internal_api_base,
                page_overrides=page_overrides,
            )
        ),
        _maybe_syspath(extra_sys_path),
    ):
        return at.run()


@dataclass(frozen=True)
class FluxLitTestClient:
    """Test harness that mirrors production routing (API prefix + gateway).

    **API** — :attr:`api` is a Starlette :class:`~starlette.testclient.TestClient` wired
    through :func:`fluxlit.gateway.build_gateway`, so paths include the configured
    ``api_prefix`` and ``/healthz`` behaves like production.

    **Public mount** — Set ``root_mount`` (or :meth:`with_root_path`) to simulate
    Workbench / Posit-style URLs where the browser path is ``{mount}{api_prefix}/…``.
    Use :meth:`api_get` / :meth:`api_post` so URLs are built correctly; optional
    ``root_path=`` on a single call builds a matching gateway for that request only.

    **Streamlit** — :meth:`streamlit` runs ``AppTest`` against :mod:`fluxlit.streamlit.main`
    with the same environment variables the runtime sets.

    **AppTest multipage** — :meth:`assert_no_streamlit_exception` fails on ``st.error`` /
    ``st.exception``. :meth:`select_page` sets ``?page=`` and reruns; the entrypoint
    honors :func:`fluxlit.deep_links.match_nav_page` before :func:`streamlit.navigation`.
    Module-level :func:`apptest_assert_no_errors`, :func:`assert_no_streamlit_exception`,
    and :func:`apptest_select_page` mirror the same behavior.
    """

    app: FluxLit[Any]
    api_prefix: str = "/api"
    root_mount: str = ""

    def _normalized_api_prefix(self) -> str:
        return normalize_api_mount_path(self.api_prefix)

    def _effective_mount(self, root_path: str | None) -> str:
        if root_path is not None:
            return normalize_root_mount(root_path)
        return normalize_root_mount(self.root_mount)

    def _public_api_url(self, path: str, *, root_path: str | None) -> str:
        p = path if path.startswith("/") else f"/{path}"
        mount = self._effective_mount(root_path)
        core = f"{self._normalized_api_prefix()}{p}"
        return f"{mount}{core}" if mount else core

    def _gateway_client(self, root_path: str | None) -> TestClient:
        mount = self._effective_mount(root_path)
        gateway = build_gateway(
            self.app.api,
            "http://127.0.0.1:9",
            api_prefix=self.api_prefix,
            root_mount=mount,
            access_log=self.app.settings.enable_gateway_access_log,
            proxy_settings=self.app.settings,
        )
        return TestClient(gateway)

    @property
    def api(self) -> TestClient:
        """HTTP test client; non-API routes hit a dummy upstream (unused for ``/api`` tests)."""
        return self._gateway_client(None)

    def with_root_path(self, root_path: str) -> FluxLitTestClient:
        """Return a copy of this client with a browser-visible path prefix (Workbench-style)."""
        return replace(self, root_mount=normalize_root_mount(root_path))

    def api_get(self, path: str, *, root_path: str | None = None, **kwargs: Any) -> httpx.Response:
        """``GET`` relative to ``api_prefix`` (leading slash optional on ``path``).

        When ``root_path`` is set, the request uses that public mount for this call only
        (a separate gateway instance). Omit it to use :attr:`root_mount` on this client.
        """
        url = self._public_api_url(path, root_path=root_path)
        return self._gateway_client(root_path).get(url, **kwargs)

    def api_post(self, path: str, *, root_path: str | None = None, **kwargs: Any) -> httpx.Response:
        """``POST`` relative to ``api_prefix`` (optional per-call ``root_path``)."""
        url = self._public_api_url(path, root_path=root_path)
        return self._gateway_client(root_path).post(url, **kwargs)

    def openapi(self) -> dict[str, Any]:
        """Fetch and parse ``GET {api_prefix}/openapi.json``; raises if not a JSON object."""
        data = self.api_get("/openapi.json").json()
        if not isinstance(data, dict):
            msg = "OpenAPI response was not a JSON object."
            raise TypeError(msg)
        return data

    def assert_docs_available(self, *, root_path: str | None = None) -> None:
        """Assert OpenAPI JSON and Swagger UI are reachable through the gateway.

        Raises:
            AssertionError: If OpenAPI is missing/invalid or ``GET …/docs`` is not
                available (including when FastAPI ``docs_url`` is disabled).
        """
        spec = self.api_get("/openapi.json", root_path=root_path)
        spec.raise_for_status()
        body = spec.json()
        if not isinstance(body, dict) or "openapi" not in body:
            msg = "OpenAPI JSON missing or invalid."
            raise AssertionError(msg)
        doc = self.api_get("/docs", root_path=root_path, follow_redirects=False)
        if doc.status_code == 404:
            msg = "Swagger UI not available at /docs (docs_url disabled on FastAPI?)."
            raise AssertionError(msg)
        if doc.status_code not in (200, 307, 308):
            msg = f"Unexpected GET /docs status: {doc.status_code}"
            raise AssertionError(msg)

    def streamlit(
        self,
        *,
        target: str,
        internal_api_base: str | None = None,
        extra_sys_path: str | Path | None = None,
        query_params: dict[str, str] | None = None,
        page_overrides: dict[str, Any] | None = None,
    ) -> Any:
        """Execute Streamlit's ``AppTest`` against :mod:`fluxlit.streamlit.main`.

        Requires Streamlit >= 1.30 for ``AppTest``. Patches ``FLUXLIT_APP``,
        ``FLUXLIT_INTERNAL_API_BASE``, ``FLUXLIT_API_PREFIX``, and ``FLUXLIT_TESTS`` for
        the duration of the run.

        Args:
            target: Import path ``module:FluxLit`` (same as CLI).
            internal_api_base: Override internal API URL; default is a placeholder with
                the correct ``api_prefix`` suffix.
            extra_sys_path: Optional directory prepended to ``sys.path`` (e.g. project root).
            query_params: Optional initial query string values (same as assigning to
                ``AppTest.query_params`` before the first ``run()``).
            page_overrides: Optional JSON-serializable map merged into handler dependency
                injection (via ``FLUXLIT_TEST_PAGE_OVERRIDES``) for ``Header`` / test doubles.

        Returns:
            The result of ``AppTest.from_file(...).run()`` (Streamlit type).
        """
        streamlit = _import_streamlit()
        if tuple(int(x) for x in streamlit.__version__.split(".")[:2]) < (1, 30):
            msg = "Streamlit AppTest is not available in this Streamlit version."
            raise RuntimeError(msg)

        from streamlit.testing.v1 import AppTest

        entry = streamlit_main_path()

        with (
            _patched_env(
                _streamlit_apptest_env(
                    self,
                    target=target,
                    internal_api_base=internal_api_base,
                    page_overrides=page_overrides,
                )
            ),
            _maybe_syspath(extra_sys_path),
        ):
            at = AppTest.from_file(str(entry))
            if query_params:
                for key, value in query_params.items():
                    at.query_params[key] = value
            return at.run()

    def assert_no_streamlit_exception(self, at: Any) -> None:
        """Fail if *at* collected ``st.exception`` or ``st.error`` blocks."""
        apptest_assert_no_errors(at)

    def select_page(
        self,
        at: Any,
        page: str,
        *,
        target: str,
        internal_api_base: str | None = None,
        extra_sys_path: str | Path | None = None,
        page_key: str = "page",
        page_overrides: dict[str, Any] | None = None,
    ) -> Any:
        """Set query key and ``run()`` again with ``target`` env (same patch as ``streamlit``)."""
        return apptest_select_page(
            at,
            self,
            target=target,
            page=page,
            internal_api_base=internal_api_base,
            extra_sys_path=extra_sys_path,
            page_key=page_key,
            page_overrides=page_overrides,
        )


def _import_streamlit() -> Any:
    try:
        import streamlit

        return streamlit
    except Exception as e:  # pragma: no cover
        msg = "Streamlit is required to use FluxLitTestClient.streamlit()."
        raise RuntimeError(msg) from e


@contextlib.contextmanager
def _patched_env(values: dict[str, str]) -> Iterator[None]:
    old = {k: os.environ.get(k) for k in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


@contextlib.contextmanager
def _maybe_syspath(extra: str | Path | None) -> Iterator[None]:
    if extra is None:
        yield
        return
    import sys

    p = str(extra)
    sys.path.insert(0, p)
    try:
        yield
    finally:
        with contextlib.suppress(ValueError):
            sys.path.remove(p)


__all__ = [
    "FluxLitTestClient",
    "apptest_assert_no_errors",
    "apptest_select_page",
    "assert_no_streamlit_exception",
    "streamlit_main_path",
]
