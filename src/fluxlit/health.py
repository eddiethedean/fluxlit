"""Readiness probes for the unified runtime (Streamlit sidecar)."""

from __future__ import annotations

import httpx

from fluxlit.config import FluxlitSettings
from fluxlit.runtime import read_streamlit_upstream_url


def _streamlit_readiness_urls(upstream: str) -> list[str]:
    """Candidate Streamlit URLs that indicate the sidecar is serving traffic."""
    base = upstream.rstrip("/")
    urls = [f"{base}/"]
    mount = FluxlitSettings().public_mount_path().strip().strip("/")
    if mount:
        urls.append(f"{base}/{mount}/")
    return urls


async def probe_streamlit_ready(*, timeout_s: float = 0.5) -> tuple[bool, str]:
    """Return ``(ok, detail)`` for whether the Streamlit upstream accepts HTTP traffic.

    When ``FLUXLIT_STREAMLIT_UPSTREAM`` / file state is unset (typical in bare FastAPI
    tests), returns ``(True, "not_configured")``.

    When configured, readiness requires an HTTP **2xx** response from ``GET`` on the
    upstream root (``{upstream}/``). Other status codes (including 3xx/4xx) are treated
    as not ready so Kubernetes-style probes reflect a healthy Streamlit app.
    """
    upstream = read_streamlit_upstream_url()
    if not upstream:
        return True, "not_configured"
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            detail = ""
            for url in _streamlit_readiness_urls(upstream):
                response = await client.get(url)
                if 200 <= response.status_code < 300:
                    return True, "ok"
                detail = f"upstream_http_{response.status_code}"
    except (httpx.HTTPError, OSError) as e:
        # Some Win32 socket errors stringify to "", but tests/ops want a non-empty reason.
        detail = str(e) or f"{type(e).__name__}: {e!r}"
        return False, detail
    return False, detail
