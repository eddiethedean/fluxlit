"""HTTP client for calling the FastAPI app from Streamlit (server-side, same process host)."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, TypeAdapter

from fluxlit.logging_context import REQUEST_ID_HEADER, get_request_id

T = TypeVar("T")

AuthHeaderFactory = Callable[[], Mapping[str, str]]


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
        default_headers: Mapping[str, str] | None = None,
        auth_header_factory: AuthHeaderFactory | None = None,
        propagate_request_id: bool = False,
    ) -> None:
        """
        Args:
            base_url: API root including mount prefix. Falls back to
                ``FLUXLIT_INTERNAL_API_BASE`` or ``http://127.0.0.1:8000/api``.
            timeout: Per-request timeout in seconds.
            default_headers: Merged into each request (caller headers override on key clash).
            auth_header_factory: Callable returning headers (e.g. ``Authorization``) per request.
                Use instead of putting long-lived secrets in Streamlit widget state.
            propagate_request_id: If True, send ``X-Request-ID`` when
                :func:`fluxlit.logging_context.get_request_id` is set (usually empty in Streamlit).
        """
        env_base = os.environ.get("FLUXLIT_INTERNAL_API_BASE", "").rstrip("/")
        resolved = (base_url or env_base or "http://127.0.0.1:8000/api").rstrip("/")
        self._default_headers = dict(default_headers) if default_headers else {}
        self._auth_header_factory = auth_header_factory
        self._propagate_request_id = propagate_request_id
        self._client = httpx.Client(base_url=resolved, timeout=timeout)

    @classmethod
    def for_fluxlit(
        cls,
        *,
        bearer_token: str | None = None,
        auth_header_factory: AuthHeaderFactory | None = None,
        **kwargs: Any,
    ) -> ApiClient:
        """Convenience constructor with static bearer token or factory (mutually exclusive)."""
        if bearer_token is not None and auth_header_factory is not None:
            msg = "Pass only one of bearer_token or auth_header_factory"
            raise TypeError(msg)
        factory: AuthHeaderFactory | None = auth_header_factory
        if bearer_token is not None:
            token = bearer_token

            def factory() -> Mapping[str, str]:
                return {"Authorization": f"Bearer {token}"}

        return cls(auth_header_factory=factory, **kwargs)

    def _merge_headers(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        headers = dict(self._default_headers)
        user = kwargs.get("headers")
        if user:
            headers.update(user)
        if self._auth_header_factory:
            headers.update(self._auth_header_factory())
        if self._propagate_request_id:
            rid = get_request_id()
            if rid:
                headers.setdefault(REQUEST_ID_HEADER, rid)
        kwargs = {**kwargs, "headers": headers}
        return kwargs

    def request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        """Send a request; ``path`` may omit a leading slash."""
        url = path if path.startswith("/") else f"/{path}"
        merged = self._merge_headers(dict(kwargs))
        return self._client.request(method, url, **merged)

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
            kwargs: Forwarded to :meth:`get`.
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
            kwargs: Forwarded to :meth:`post`.
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
