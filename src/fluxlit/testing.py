"""Test helpers: gateway-scoped HTTP client and Streamlit ``AppTest`` integration."""

from __future__ import annotations

import contextlib
import os
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from starlette.testclient import TestClient

from fluxlit.app import FluxLit
from fluxlit.gateway import build_gateway


@dataclass(frozen=True)
class FluxLitTestClient:
    """Test harness that mirrors production routing (API prefix + gateway).

    **API:** :attr:`api` is a Starlette :class:`~starlette.testclient.TestClient` wired
    through :func:`fluxlit.gateway.build_gateway`, so paths include the configured
    ``api_prefix`` and ``/healthz`` behaves like production.

    **Streamlit:** :meth:`streamlit` runs ``AppTest`` against :mod:`fluxlit.streamlit_main`
    with the same environment variables the runtime sets.

    Attributes:
        app: :class:`~fluxlit.app.FluxLit` instance under test.
        api_prefix: Public API mount path for :func:`~fluxlit.gateway.build_gateway`.
    """

    app: FluxLit
    api_prefix: str = "/api"

    @property
    def api(self) -> TestClient:
        """HTTP test client; non-API routes hit a dummy upstream (unused for ``/api`` tests)."""
        gateway = build_gateway(self.app.api, "http://127.0.0.1:9", api_prefix=self.api_prefix)
        return TestClient(gateway)

    def api_get(self, path: str, **kwargs: Any) -> httpx.Response:
        """``GET`` relative to ``api_prefix`` (leading slash optional on ``path``)."""
        p = path if path.startswith("/") else f"/{path}"
        return self.api.get(f"{self.api_prefix}{p}", **kwargs)

    def api_post(self, path: str, **kwargs: Any) -> httpx.Response:
        """``POST`` relative to ``api_prefix``."""
        p = path if path.startswith("/") else f"/{path}"
        return self.api.post(f"{self.api_prefix}{p}", **kwargs)

    def openapi(self) -> dict[str, Any]:
        """Fetch and parse ``GET {api_prefix}/openapi.json``; raises if not a JSON object."""
        data = self.api_get("/openapi.json").json()
        if not isinstance(data, dict):
            msg = "OpenAPI response was not a JSON object."
            raise TypeError(msg)
        return data

    def streamlit(
        self,
        *,
        target: str,
        internal_api_base: str | None = None,
        extra_sys_path: str | Path | None = None,
    ) -> Any:
        """Execute Streamlit's ``AppTest`` against :mod:`fluxlit.streamlit_main`.

        Requires Streamlit >= 1.30 for ``AppTest``. Patches ``FLUXLIT_APP``,
        ``FLUXLIT_INTERNAL_API_BASE``, and ``FLUXLIT_API_PREFIX`` for the duration of the run.

        Args:
            target: Import path ``module:FluxLit`` (same as CLI).
            internal_api_base: Override internal API URL; default is a placeholder with
                the correct ``api_prefix`` suffix.
            extra_sys_path: Optional directory prepended to ``sys.path`` (e.g. project root).

        Returns:
            The result of ``AppTest.from_file(...).run()`` (Streamlit type).
        """
        streamlit = _import_streamlit()
        if tuple(int(x) for x in streamlit.__version__.split(".")[:2]) < (1, 30):
            msg = "Streamlit AppTest is not available in this Streamlit version."
            raise RuntimeError(msg)

        from streamlit.testing.v1 import AppTest

        entry = Path(__file__).resolve().parent / "streamlit_main.py"
        internal = internal_api_base or f"http://127.0.0.1:1{self.api_prefix}"

        with (
            _patched_env(
                {
                    "FLUXLIT_APP": target,
                    "FLUXLIT_INTERNAL_API_BASE": internal,
                    "FLUXLIT_API_PREFIX": self.api_prefix,
                }
            ),
            _maybe_syspath(extra_sys_path),
        ):
            return AppTest.from_file(str(entry)).run()


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
