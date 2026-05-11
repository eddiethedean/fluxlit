"""Tests for the Streamlit file watcher used with ``--reload-scope=full``."""

from __future__ import annotations

import time

import pytest

from fluxlit.runtime import _start_streamlit_reload_watcher


def test_reload_watcher_invokes_callback_on_watch_yield(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_watch(*_args: object, **_kwargs: object):
        yield frozenset()

    monkeypatch.setattr("watchfiles.watch", fake_watch)
    calls: list[int] = []
    done = {"v": False}

    def on_change() -> None:
        calls.append(1)
        done["v"] = True

    def stop_flag() -> bool:
        return done["v"]

    _start_streamlit_reload_watcher(on_change, debounce_s=0.01, stop_flag=stop_flag)
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and not calls:
        time.sleep(0.02)
    assert calls == [1]
