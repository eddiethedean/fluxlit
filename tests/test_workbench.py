"""Tests for :mod:`fluxlit.runtime.workbench` and Workbench CLI wiring."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from fluxlit.cli import app
from fluxlit.runtime.workbench import (
    browser_base_url,
    format_workbench_startup_message,
    loopback_browser_host,
)


@pytest.mark.parametrize(
    ("bind", "expected"),
    [
        ("0.0.0.0", "127.0.0.1"),
        ("::", "127.0.0.1"),
        ("[::]", "127.0.0.1"),
        ("10.0.0.5", "10.0.0.5"),
        ("", "127.0.0.1"),
    ],
)
def test_loopback_browser_host(bind: str, expected: str) -> None:
    assert loopback_browser_host(bind) == expected


def test_browser_base_url_scheme_fallback() -> None:
    assert browser_base_url("0.0.0.0", 8080) == "http://127.0.0.1:8080"
    assert browser_base_url("127.0.0.1", 1, scheme="") == "http://127.0.0.1:1"
    assert browser_base_url("127.0.0.1", 2, scheme="   ") == "http://127.0.0.1:2"


def test_format_workbench_startup_message_mount_and_oauth() -> None:
    text = format_workbench_startup_message(
        app_title="Demo",
        bind_host="0.0.0.0",
        bind_port=8000,
        root_mount_norm="/content/1",
        api_mount_path="/api",
        public_base_url="https://example.com/content/1",
        proxy_headers_on=True,
    )
    assert "Workbench/Connect mode" in text
    assert "http://127.0.0.1:8000/content/1/" in text
    assert "http://127.0.0.1:8000/content/1/api/healthz" in text
    assert "http://127.0.0.1:8000/content/1/api/docs" in text
    assert "FLUXLIT_ROOT_PATH" not in text  # mount set — no missing-prefix hint
    assert "OAuth / canonical" in text


def test_format_workbench_startup_message_no_mount_hint() -> None:
    text = format_workbench_startup_message(
        app_title="T",
        bind_host="127.0.0.1",
        bind_port=9,
        root_mount_norm="",
        api_mount_path="v1",
        public_base_url="",
        proxy_headers_on=False,
    )
    assert "FLUXLIT_ROOT_PATH" in text
    assert "http://127.0.0.1:9/v1/healthz" in text
    assert "X-Forwarded" not in text


def test_format_workbench_startup_message_default_title() -> None:
    text = format_workbench_startup_message(
        app_title="",
        bind_host="127.0.0.1",
        bind_port=1,
        root_mount_norm="/z",
        api_mount_path="/api",
        public_base_url="",
        proxy_headers_on=True,
    )
    assert "App title: FluxLit" in text


def test_workbench_cli_invokes_run_unified_with_workbench_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "wb_app.py").write_text(
        "from fluxlit import FluxLit\napp = FluxLit(title='WB')\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    called: dict[str, object] = {}

    def fake_run_unified(target: str, **kwargs: object) -> None:
        called["target"] = target
        called.update(kwargs)

    monkeypatch.setattr("fluxlit.cli.run_unified", fake_run_unified)

    runner = CliRunner()
    res = runner.invoke(app, ["workbench", "wb_app:app"], catch_exceptions=False)
    assert res.exit_code == 0
    assert called["workbench_mode"] is True
    assert called["proxy_headers"] is True


def test_dev_workbench_flag_sets_workbench_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "dwb.py").write_text(
        "from fluxlit import FluxLit\napp = FluxLit()\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    called: dict[str, object] = {}

    def fake_run_unified(target: str, **kwargs: object) -> None:
        called.update(kwargs)

    monkeypatch.setattr("fluxlit.cli.run_unified", fake_run_unified)
    runner = CliRunner()
    res = runner.invoke(app, ["dev", "dwb:app", "--workbench"], catch_exceptions=False)
    assert res.exit_code == 0
    assert called["workbench_mode"] is True
    assert called["proxy_headers"] is True
