"""Streamlit upstream URL persistence (temp file + environment)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

STREAMLIT_UPSTREAM_FILE_ENV = "FLUXLIT_STREAMLIT_UPSTREAM_FILE"


def read_streamlit_upstream_url() -> str:
    """Current Streamlit base URL from :func:`write_streamlit_upstream_state` or plain env."""
    fp = (os.environ.get(STREAMLIT_UPSTREAM_FILE_ENV) or "").strip()
    if fp:
        try:
            raw = Path(fp).read_text(encoding="utf-8").strip()
        except OSError:
            raw = ""
        if raw:
            return raw.rstrip("/")
    return (os.environ.get("FLUXLIT_STREAMLIT_UPSTREAM") or "").strip().rstrip("/")


def write_streamlit_upstream_state(url: str) -> Path:
    """Write *url* to a temp file and set env for the gateway resolver and subprocesses."""
    fd, name = tempfile.mkstemp(prefix="fluxlit-upstream-", suffix=".txt", text=True)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(url.strip())
    path = Path(name)
    os.environ["FLUXLIT_STREAMLIT_UPSTREAM"] = url.strip()
    os.environ[STREAMLIT_UPSTREAM_FILE_ENV] = str(path)
    return path


def update_streamlit_upstream_file(path: Path, url: str) -> None:
    """Replace the on-disk upstream URL (e.g. after restarting Streamlit on a new port)."""
    path.write_text(url.strip(), encoding="utf-8")
    os.environ["FLUXLIT_STREAMLIT_UPSTREAM"] = url.strip()
