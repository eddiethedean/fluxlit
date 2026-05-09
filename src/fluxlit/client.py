from __future__ import annotations

import os
from typing import Any

import httpx


class ApiClient:
    """HTTP client for calling the mounted FastAPI app from Streamlit (server-side)."""

    def __init__(
        self,
        base_url: str | None = None,
        *,
        timeout: float = 30.0,
    ) -> None:
        env_base = os.environ.get("FLUXLIT_INTERNAL_API_BASE", "").rstrip("/")
        resolved = (base_url or env_base or "http://127.0.0.1:8000/api").rstrip("/")
        self._client = httpx.Client(base_url=resolved, timeout=timeout)

    def request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        url = path if path.startswith("/") else f"/{path}"
        return self._client.request(method, url, **kwargs)

    def get(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.request("PUT", path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.request("DELETE", path, **kwargs)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> ApiClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
