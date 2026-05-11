"""TCP wait helper (separate module so tests can monkeypatch ``fluxlit.runtime._wait_for_tcp``)."""

from __future__ import annotations

import socket
import time


def _wait_for_tcp(host: str, port: int, timeout_s: float = 30.0) -> None:
    """Block until ``host:port`` accepts a TCP connection or ``timeout_s`` elapses."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.05)
    msg = f"Timed out waiting for {host}:{port}"
    raise TimeoutError(msg)


def _invoke_wait_for_tcp(host: str, port: int, timeout_s: float = 30.0) -> None:
    """Delegate to :data:`fluxlit.runtime._wait_for_tcp` so monkeypatches on the package work."""
    import fluxlit.runtime as rt

    rt._wait_for_tcp(host, port, timeout_s)
