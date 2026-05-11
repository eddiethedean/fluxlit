"""Shared runtime constants (TCP wait, pidfile name)."""

from __future__ import annotations

DEFAULT_PIDFILE_NAME = ".fluxlit-dev.pid"
# Streamlit cold start can exceed the default 30s on slow disks / CI.
_STREAMLIT_TCP_WAIT_S = 60.0
