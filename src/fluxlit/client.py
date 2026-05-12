"""HTTP client for calling the FastAPI app from Streamlit (server-side, same process host)."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from typing import TypeVar

import httpx
from httpx import USE_CLIENT_DEFAULT
from httpx._client import UseClientDefault  # noqa: PLC2701 — public type surface for defaults
from httpx._types import (  # noqa: PLC2701 — mirrors httpx Client.request annotations
    AuthTypes,
    CookieTypes,
    HeaderTypes,
    QueryParamTypes,
    RequestContent,
    RequestData,
    RequestExtensions,
    RequestFiles,
    TimeoutTypes,
)
from pydantic import BaseModel, TypeAdapter

from fluxlit.config import JsonValue
from fluxlit.logging import REQUEST_ID_HEADER, get_request_id

T = TypeVar("T")

AuthHeaderFactory = Callable[[], Mapping[str, str]]


class ApiClient:
    """Sync HTTPX client scoped to your gateway-mounted API.

    Paths are relative to the API base (including the ``/api`` prefix in the base URL).
    For example use ``client.get("/users")``, not ``client.get("/api/users")``.

    Use :meth:`for_fluxlit` or :meth:`with_bearer` when routes require ``Authorization``.

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
                Use instead of putting long-lived secrets in Streamlit widget state. Per-call
                ``headers`` override these generated headers on key clash.
            propagate_request_id: If True, send ``X-Request-ID`` when
                :func:`fluxlit.logging.get_request_id` is set (usually empty in Streamlit).
        """
        env_base = os.environ.get("FLUXLIT_INTERNAL_API_BASE", "").rstrip("/")
        resolved = (base_url or env_base or "http://127.0.0.1:8000/api").rstrip("/")
        self._resolved_base = resolved
        self._timeout = timeout
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
        base_url: str | None = None,
        timeout: float = 30.0,
        default_headers: Mapping[str, str] | None = None,
        propagate_request_id: bool = False,
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

        return cls(
            base_url=base_url,
            timeout=timeout,
            default_headers=default_headers,
            auth_header_factory=factory,
            propagate_request_id=propagate_request_id,
        )

    def with_bearer(self, bearer_token: str) -> ApiClient:
        """Return a new client with the same base URL and options plus ``Authorization: Bearer``.

        Use on the **injected page client** (no auth by default) when you already have a
        token in ``st.session_state`` and want the same :class:`ApiClient` surface without
        calling :meth:`for_fluxlit`. If this client already has an ``auth_header_factory``,
        the new factory merges those headers first, then sets ``Authorization`` to this
        bearer (call-time headers still win on key clash).

        The returned client owns a separate ``httpx`` connection pool; close it when done
        or use a ``with`` block.
        """
        parent_factory = self._auth_header_factory

        def factory() -> Mapping[str, str]:
            merged: dict[str, str] = dict(parent_factory()) if parent_factory else {}
            merged["Authorization"] = f"Bearer {bearer_token}"
            return merged

        return ApiClient(
            self._resolved_base,
            timeout=self._timeout,
            default_headers=dict(self._default_headers),
            auth_header_factory=factory,
            propagate_request_id=self._propagate_request_id,
        )

    def _build_request_headers(self, headers: HeaderTypes | None) -> HeaderTypes:
        merged = httpx.Headers(self._default_headers)
        if self._auth_header_factory:
            merged.update(self._auth_header_factory())
        if headers is not None:
            merged.update(headers)
        if self._propagate_request_id:
            rid = get_request_id()
            if rid:
                merged.setdefault(REQUEST_ID_HEADER, rid)
        return merged

    def request(
        self,
        method: str,
        path: str,
        *,
        content: RequestContent | None = None,
        data: RequestData | None = None,
        files: RequestFiles | None = None,
        json: JsonValue | None = None,
        params: QueryParamTypes | None = None,
        headers: HeaderTypes | None = None,
        cookies: CookieTypes | None = None,
        auth: AuthTypes | UseClientDefault | None = USE_CLIENT_DEFAULT,
        follow_redirects: bool | UseClientDefault = USE_CLIENT_DEFAULT,
        timeout: TimeoutTypes | UseClientDefault = USE_CLIENT_DEFAULT,
        extensions: RequestExtensions | None = None,
    ) -> httpx.Response:
        """Send a request; ``path`` may omit a leading slash."""
        url = path if path.startswith("/") else f"/{path}"
        merged_headers = self._build_request_headers(headers)
        return self._client.request(
            method,
            url,
            content=content,
            data=data,
            files=files,
            json=json,
            params=params,
            headers=merged_headers,
            cookies=cookies,
            auth=auth,
            follow_redirects=follow_redirects,
            timeout=timeout,
            extensions=extensions,
        )

    def get(
        self,
        path: str,
        *,
        params: QueryParamTypes | None = None,
        headers: HeaderTypes | None = None,
        cookies: CookieTypes | None = None,
        auth: AuthTypes | UseClientDefault | None = USE_CLIENT_DEFAULT,
        follow_redirects: bool | UseClientDefault = USE_CLIENT_DEFAULT,
        timeout: TimeoutTypes | UseClientDefault = USE_CLIENT_DEFAULT,
        extensions: RequestExtensions | None = None,
    ) -> httpx.Response:
        """``GET`` request."""
        return self.request(
            "GET",
            path,
            params=params,
            headers=headers,
            cookies=cookies,
            auth=auth,
            follow_redirects=follow_redirects,
            timeout=timeout,
            extensions=extensions,
        )

    def post(
        self,
        path: str,
        *,
        content: RequestContent | None = None,
        data: RequestData | None = None,
        files: RequestFiles | None = None,
        json: JsonValue | None = None,
        params: QueryParamTypes | None = None,
        headers: HeaderTypes | None = None,
        cookies: CookieTypes | None = None,
        auth: AuthTypes | UseClientDefault | None = USE_CLIENT_DEFAULT,
        follow_redirects: bool | UseClientDefault = USE_CLIENT_DEFAULT,
        timeout: TimeoutTypes | UseClientDefault = USE_CLIENT_DEFAULT,
        extensions: RequestExtensions | None = None,
    ) -> httpx.Response:
        """``POST`` request."""
        return self.request(
            "POST",
            path,
            content=content,
            data=data,
            files=files,
            json=json,
            params=params,
            headers=headers,
            cookies=cookies,
            auth=auth,
            follow_redirects=follow_redirects,
            timeout=timeout,
            extensions=extensions,
        )

    def put(
        self,
        path: str,
        *,
        content: RequestContent | None = None,
        data: RequestData | None = None,
        files: RequestFiles | None = None,
        json: JsonValue | None = None,
        params: QueryParamTypes | None = None,
        headers: HeaderTypes | None = None,
        cookies: CookieTypes | None = None,
        auth: AuthTypes | UseClientDefault | None = USE_CLIENT_DEFAULT,
        follow_redirects: bool | UseClientDefault = USE_CLIENT_DEFAULT,
        timeout: TimeoutTypes | UseClientDefault = USE_CLIENT_DEFAULT,
        extensions: RequestExtensions | None = None,
    ) -> httpx.Response:
        """``PUT`` request."""
        return self.request(
            "PUT",
            path,
            content=content,
            data=data,
            files=files,
            json=json,
            params=params,
            headers=headers,
            cookies=cookies,
            auth=auth,
            follow_redirects=follow_redirects,
            timeout=timeout,
            extensions=extensions,
        )

    def delete(
        self,
        path: str,
        *,
        params: QueryParamTypes | None = None,
        headers: HeaderTypes | None = None,
        cookies: CookieTypes | None = None,
        auth: AuthTypes | UseClientDefault | None = USE_CLIENT_DEFAULT,
        follow_redirects: bool | UseClientDefault = USE_CLIENT_DEFAULT,
        timeout: TimeoutTypes | UseClientDefault = USE_CLIENT_DEFAULT,
        extensions: RequestExtensions | None = None,
    ) -> httpx.Response:
        """``DELETE`` request."""
        return self.request(
            "DELETE",
            path,
            params=params,
            headers=headers,
            cookies=cookies,
            auth=auth,
            follow_redirects=follow_redirects,
            timeout=timeout,
            extensions=extensions,
        )

    def get_model(
        self,
        path: str,
        model: type[T],
        *,
        params: QueryParamTypes | None = None,
        headers: HeaderTypes | None = None,
        cookies: CookieTypes | None = None,
        auth: AuthTypes | UseClientDefault | None = USE_CLIENT_DEFAULT,
        follow_redirects: bool | UseClientDefault = USE_CLIENT_DEFAULT,
        timeout: TimeoutTypes | UseClientDefault = USE_CLIENT_DEFAULT,
        extensions: RequestExtensions | None = None,
    ) -> T:
        """``GET`` and parse JSON into a Pydantic model (raises on 4xx/5xx or validation).

        Args:
            path: Relative API path.
            model: Pydantic model type for the response body.
            Remaining kwargs: forwarded to :meth:`get`.
        """
        response = self.get(
            path,
            params=params,
            headers=headers,
            cookies=cookies,
            auth=auth,
            follow_redirects=follow_redirects,
            timeout=timeout,
            extensions=extensions,
        )
        response.raise_for_status()
        return TypeAdapter(model).validate_json(response.content)

    def post_model(
        self,
        path: str,
        response_model: type[T],
        *,
        body: BaseModel | Mapping[str, JsonValue] | None = None,
        content: RequestContent | None = None,
        data: RequestData | None = None,
        files: RequestFiles | None = None,
        json: JsonValue | None = None,
        params: QueryParamTypes | None = None,
        headers: HeaderTypes | None = None,
        cookies: CookieTypes | None = None,
        auth: AuthTypes | UseClientDefault | None = USE_CLIENT_DEFAULT,
        follow_redirects: bool | UseClientDefault = USE_CLIENT_DEFAULT,
        timeout: TimeoutTypes | UseClientDefault = USE_CLIENT_DEFAULT,
        extensions: RequestExtensions | None = None,
    ) -> T:
        """``POST`` JSON body and parse the response as ``response_model``.

        Args:
            path: Relative API path.
            response_model: Pydantic model type for the response body.
            body: Request JSON (from ``model_dump()`` if a :class:`~pydantic.BaseModel`).
                Mutually exclusive with ``json``.
            Remaining kwargs: forwarded to :meth:`post`.
        """
        if body is not None and json is not None:
            msg = "Pass only one of body or json"
            raise TypeError(msg)
        json_body: JsonValue | None
        if isinstance(body, BaseModel):
            json_body = body.model_dump(mode="json")
        else:
            json_body = dict(body) if body is not None else json
        response = self.post(
            path,
            content=content,
            data=data,
            files=files,
            json=json_body,
            params=params,
            headers=headers,
            cookies=cookies,
            auth=auth,
            follow_redirects=follow_redirects,
            timeout=timeout,
            extensions=extensions,
        )
        response.raise_for_status()
        return TypeAdapter(response_model).validate_json(response.content)

    def close(self) -> None:
        """Close the underlying HTTPX client."""
        self._client.close()

    def __enter__(self) -> ApiClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
