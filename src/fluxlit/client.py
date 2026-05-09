"""HTTP client for calling the FastAPI app from Streamlit (server-side, same process host)."""

from __future__ import annotations

import os
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, TypeAdapter

T = TypeVar("T")


class ApiClient:
    """Sync HTTPX client scoped to your gateway-mounted API.

    Paths are relative to the API base (including the ``/api`` prefix in the base URL).
    For example use ``client.get("/users")``, not ``client.get("/api/users")``.

    The runtime sets ``FLUXLIT_INTERNAL_API_BASE`` (e.g. ``http://127.0.0.1:8000/api``)
    for Streamlit subprocesses so defaults work without passing ``base_url``.
    """

    def __init__(
        self,
        base_url: str | None = None,
        *,
        timeout: float = 30.0,
    ) -> None:
        """
        Args:
            base_url: API root including mount prefix. Falls back to
                ``FLUXLIT_INTERNAL_API_BASE`` or ``http://127.0.0.1:8000/api``.
            timeout: Per-request timeout in seconds.
        """
        env_base = os.environ.get("FLUXLIT_INTERNAL_API_BASE", "").rstrip("/")
        resolved = (base_url or env_base or "http://127.0.0.1:8000/api").rstrip("/")
        self._client = httpx.Client(base_url=resolved, timeout=timeout)

    def request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        """Send a request; ``path`` may omit a leading slash."""
        url = path if path.startswith("/") else f"/{path}"
        return self._client.request(method, url, **kwargs)

    def get(self, path: str, **kwargs: Any) -> httpx.Response:
        """``GET`` request."""
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> httpx.Response:
        """``POST`` request."""
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs: Any) -> httpx.Response:
        """``PUT`` request."""
        return self.request("PUT", path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> httpx.Response:
        """``DELETE`` request."""
        return self.request("DELETE", path, **kwargs)

    def get_model(self, path: str, model: type[T], **kwargs: Any) -> T:
        """``GET`` and parse JSON into a Pydantic model (raises on 4xx/5xx or validation).

        Args:
            path: Relative API path.
            model: Pydantic model type for the response body.
            **kwargs: Forwarded to :meth:`get`.
        """
        response = self.get(path, **kwargs)
        response.raise_for_status()
        return TypeAdapter(model).validate_json(response.content)

    def post_model(
        self,
        path: str,
        response_model: type[T],
        *,
        body: BaseModel | dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> T:
        """``POST`` JSON body and parse the response as ``response_model``.

        Args:
            path: Relative API path.
            response_model: Pydantic model type for the response body.
            body: Request JSON (from ``model_dump()`` if a :class:`~pydantic.BaseModel`).
            **kwargs: Forwarded to :meth:`post`.
        """
        json_body = body.model_dump() if isinstance(body, BaseModel) else body
        response = self.post(path, json=json_body, **kwargs)
        response.raise_for_status()
        return TypeAdapter(response_model).validate_json(response.content)

    def close(self) -> None:
        """Close the underlying HTTPX client."""
        self._client.close()

    def __enter__(self) -> ApiClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
