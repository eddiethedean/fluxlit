"""Background filesystem watch for Streamlit full-stack reload."""

from __future__ import annotations

import sys
import threading
from collections.abc import Callable
from pathlib import Path


def _start_streamlit_reload_watcher(
    on_change: Callable[[], None],
    *,
    debounce_s: float,
    stop_flag: Callable[[], bool],
) -> None:
    """Background thread: debounced filesystem watch → ``on_change`` (Streamlit restart)."""

    def run() -> None:
        try:
            from watchfiles import watch
        except ImportError:
            sys.stderr.write(
                "[fluxlit] --reload-scope=full requires the `watchfiles` package "
                "(install the same `fluxlit` environment).\n"
            )
            sys.stderr.flush()
            return
        debounce_ms = int(max(50, debounce_s * 1000))
        try:
            for _changes in watch(Path.cwd(), debounce=debounce_ms):
                if stop_flag():
                    return
                try:
                    on_change()
                except Exception as e:
                    sys.stderr.write(f"[fluxlit] Streamlit sidecar reload failed: {e}\n")
                    sys.stderr.flush()
        except Exception as e:
            sys.stderr.write(f"[fluxlit] Streamlit file watch exited: {e}\n")
            sys.stderr.flush()

    threading.Thread(target=run, daemon=True).start()
