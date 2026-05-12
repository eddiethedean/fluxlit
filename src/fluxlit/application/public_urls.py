"""Browser-visible URL helpers for :class:`~fluxlit.app.FluxLit` (mounted API + public path)."""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlencode, urlparse

from starlette.requests import Request

from fluxlit.api_mount import normalize_api_mount_path
from fluxlit.gateway.paths import normalize_root_mount

if TYPE_CHECKING:
    from fluxlit.app import FluxLit as FluxLitType


def _request_origin(request: Request) -> str:
    u = request.url
    return f"{u.scheme}://{u.netloc}".rstrip("/")


def _join_url(base: str, *parts: str) -> str:
    out = base.rstrip("/")
    for part in parts:
        if not part:
            continue
        p = part if part.startswith("/") else f"/{part}"
        out = f"{out}{p}"
    return out


class FluxLitPublicUrls:
    """Build browser-visible URLs for the Streamlit shell vs the mounted FastAPI API.

    **App base** — origin plus the public mount (``FLUXLIT_ROOT_PATH`` / ``streamlit_public_path``).
    This is where Streamlit pages live (outside the API prefix).

    **API base** — app base plus ``api_mount_path`` (default ``/api``). Liveness, readiness,
    OpenAPI, and Swagger live under this prefix on the public gateway.

    When ``FLUXLIT_PUBLIC_BASE_URL`` is set to an absolute URL, it is preferred for the
    origin (and, if it includes a path, as the app base when that path matches the
    configured public mount). Otherwise the current request's host/scheme is used
    (including ``X-Forwarded-*`` when Uvicorn proxy headers are enabled).
    """

    __slots__ = ("_fl",)

    def __init__(self, fluxlit: FluxLitType) -> None:
        self._fl = fluxlit

    def app_base(self, request: Request) -> str:
        """Return the browser-visible base URL for Streamlit (no ``api_mount_path``)."""
        s = self._fl.settings
        mount = normalize_root_mount(s.public_mount_path())
        pb = s.public_base_url.strip()
        if pb:
            pu = urlparse(pb)
            if pu.scheme and pu.netloc:
                origin = f"{pu.scheme}://{pu.netloc}".rstrip("/")
                path = (pu.path or "").rstrip("/")
                if path:
                    return pb.rstrip("/")
                if mount:
                    return _join_url(origin, mount)
                return origin
        origin = _request_origin(request)
        return _join_url(origin, mount) if mount else origin

    def api_base(self, request: Request) -> str:
        """Return the browser-visible base URL for the FastAPI app (includes ``api_mount_path``)."""
        prefix = normalize_api_mount_path(self._fl.settings.api_mount_path)
        return _join_url(self.app_base(request), prefix)

    def docs_url(self, request: Request) -> str | None:
        """Return the Swagger UI URL, or ``None`` when ``docs_url`` is disabled on ``api``."""
        du = getattr(self._fl.api, "docs_url", None)
        if du is None or du is False:
            return None
        return _join_url(self.api_base(request), str(du))

    def redoc_url(self, request: Request) -> str | None:
        """Return the ReDoc URL, or ``None`` when ``redoc_url`` is disabled on ``api``."""
        ru = getattr(self._fl.api, "redoc_url", None)
        if ru is None or ru is False:
            return None
        return _join_url(self.api_base(request), str(ru))

    def openapi_url(self, request: Request) -> str | None:
        """Return the OpenAPI JSON URL, or ``None`` when ``openapi_url`` is disabled."""
        ou = getattr(self._fl.api, "openapi_url", None)
        if ou is None or ou is False:
            return None
        return _join_url(self.api_base(request), str(ou))

    def health_url(self, request: Request) -> str:
        """Return ``GET`` liveness URL (``.../api/healthz`` by default)."""
        return _join_url(self.api_base(request), "/healthz")

    def ready_url(self, request: Request) -> str:
        """Return ``GET`` readiness URL (``.../api/readyz`` by default)."""
        return _join_url(self.api_base(request), "/readyz")

    def for_page(self, request: Request, path: str, *, query: dict[str, str] | None = None) -> str:
        """Return a browser URL for a Streamlit page path (under :meth:`app_base`, not ``/api``).

        ``path`` is a URL path such as ``"/"`` or ``"/reports"``. ``query`` values are
        percent-encoded; use this for deep links to Streamlit pages.
        """
        base = self.app_base(request).rstrip("/")
        p = path if path.startswith("/") else f"/{path}"
        url = f"{base}{p}" if p != "/" else f"{base}/"
        if query:
            url = f"{url}?{urlencode(query)}"
        return url

    def page_url(self, request: Request, path: str, *, query: dict[str, str] | None = None) -> str:
        """Alias for :meth:`for_page` (invite links, password reset, and other deep links).

        Prefer this name in app code and docs when the intent is a **shareable page URL**
        rather than an internal path join.
        """
        return self.for_page(request, path, query=query)


__all__ = ["FluxLitPublicUrls"]
