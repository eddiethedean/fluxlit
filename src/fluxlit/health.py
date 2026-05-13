"""Readiness probes for the unified runtime (Streamlit sidecar)."""

from __future__ import annotations

from urllib.parse import urlparse

import httpx

from fluxlit.config import FluxlitSettings
from fluxlit.runtime import read_streamlit_upstream_url


def _streamlit_readiness_urls(
    upstream: str, *, settings: FluxlitSettings | None = None
) -> list[str]:
    """Candidate Streamlit URLs that indicate the sidecar is serving traffic."""
    base = upstream.rstrip("/")
    urls = [f"{base}/"]
    mount = (settings or FluxlitSettings()).public_mount_path().strip().strip("/")
    if mount:
        urls.append(f"{base}/{mount}/")
    return urls


async def probe_streamlit_ready(
    *,
    timeout_s: float = 0.5,
    upstream: str | None = None,
    settings: FluxlitSettings | None = None,
) -> tuple[bool, str]:
    """Return ``(ok, detail)`` for whether the Streamlit upstream accepts HTTP traffic.

    When ``FLUXLIT_STREAMLIT_UPSTREAM`` / file state is unset (typical in bare FastAPI
    tests), returns ``(True, "not_configured")``.

    When configured, readiness requires an HTTP **2xx** response from ``GET`` on at least
    one candidate URL (see :func:`_streamlit_readiness_urls`). Other status codes are treated
    as not ready. When multiple URLs are probed and all fail, ``detail`` aggregates path and
    status (for example ``upstream_http_failed /:404;/myapp/:503``).
    """
    resolved_upstream = read_streamlit_upstream_url() if upstream is None else upstream
    if not resolved_upstream:
        return True, "not_configured"
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            failures: list[str] = []
            for url in _streamlit_readiness_urls(resolved_upstream, settings=settings):
                response = await client.get(url)
                if 200 <= response.status_code < 300:
                    return True, "ok"
                path = urlparse(url).path or "/"
                failures.append(f"{path}:{response.status_code}")
            joined = ";".join(failures)
            return False, f"upstream_http_failed {joined}"
    except (httpx.HTTPError, OSError) as e:
        # Some Win32 socket errors stringify to "", but tests/ops want a non-empty reason.
        detail = str(e) or f"{type(e).__name__}: {e!r}"
        return False, detail
