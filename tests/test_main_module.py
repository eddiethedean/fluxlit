from __future__ import annotations

import runpy
import subprocess
import sys

import pytest


def test_runpy_executes_fluxlit_main(monkeypatch: pytest.MonkeyPatch) -> None:
    """Covers :mod:`fluxlit.__main__` in-process (``python -m`` subprocess is not traced)."""
    monkeypatch.setattr(sys, "argv", ["fluxlit", "--help"])
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_module("fluxlit.__main__", run_name="__main__")
    assert excinfo.value.code == 0


def test_python_m_fluxlit_invokes_cli_help() -> None:
    """``python -m fluxlit`` loads :mod:`fluxlit.__main__` and runs :func:`fluxlit.cli.main`."""
    proc = subprocess.run(
        [sys.executable, "-m", "fluxlit", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "fluxlit" in proc.stdout.lower() or "Usage" in proc.stdout
