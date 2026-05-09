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
    """
    FluxLit-native test client.

    - **API**: a FastAPI/Starlette `TestClient` that talks to the app through the FluxLit gateway
      using the configured `api_prefix`.
    - **UI** (optional): a helper to run Streamlit's built-in `AppTest` against FluxLit's
      `streamlit_main.py` entrypoint.
    """

    app: FluxLit
    api_prefix: str = "/api"

    @property
    def api(self) -> TestClient:
        # Upstream is unused for /api routes; it just needs to be a valid URL.
        gateway = build_gateway(self.app.api, "http://127.0.0.1:9", api_prefix=self.api_prefix)
        return TestClient(gateway)

    def api_get(self, path: str, **kwargs: Any) -> httpx.Response:
        p = path if path.startswith("/") else f"/{path}"
        return self.api.get(f"{self.api_prefix}{p}", **kwargs)

    def api_post(self, path: str, **kwargs: Any) -> httpx.Response:
        p = path if path.startswith("/") else f"/{path}"
        return self.api.post(f"{self.api_prefix}{p}", **kwargs)

    def openapi(self) -> dict[str, Any]:
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
        """
        Run Streamlit's built-in `AppTest` against FluxLit's Streamlit entrypoint.

        `target` is an import string like `my_module:app` resolving to a FluxLit instance.
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
