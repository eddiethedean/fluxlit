"""Readiness probes for the unified runtime (Streamlit sidecar)."""

from __future__ import annotations

import httpx

from fluxlit.runtime import read_streamlit_upstream_url


async def probe_streamlit_ready(*, timeout_s: float = 0.5) -> tuple[bool, str]:
    """Return ``(ok, detail)`` for whether the Streamlit upstream accepts HTTP traffic.

    When ``FLUXLIT_STREAMLIT_UPSTREAM`` / file state is unset (typical in bare FastAPI
    tests), returns ``(True, "not_configured")``.
    """
    upstream = read_streamlit_upstream_url()
    if not upstream:
        return True, "not_configured"
    url = f"{upstream.rstrip('/')}/"
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            response = await client.get(url)
    except (httpx.HTTPError, OSError) as e:
        return False, str(e)
    if response.status_code < 500:
        return True, "ok"
    return False, f"upstream_http_{response.status_code}"
