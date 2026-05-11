"""Tests for Streamlit upstream file/env state used by the gateway resolver."""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

import pytest

from fluxlit.runtime import (
    STREAMLIT_UPSTREAM_FILE_ENV,
    read_streamlit_upstream_url,
    update_streamlit_upstream_file,
    write_streamlit_upstream_state,
)


@pytest.fixture(autouse=True)
def _pop_upstream_env_after_test() -> Generator[None, None, None]:
    yield
    os.environ.pop("FLUXLIT_STREAMLIT_UPSTREAM", None)
    os.environ.pop(STREAMLIT_UPSTREAM_FILE_ENV, None)


@pytest.fixture
def clean_upstream_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FLUXLIT_STREAMLIT_UPSTREAM", raising=False)
    monkeypatch.delenv(STREAMLIT_UPSTREAM_FILE_ENV, raising=False)


def test_read_streamlit_upstream_empty_when_unset(
    clean_upstream_env: None,
) -> None:
    assert read_streamlit_upstream_url() == ""


def test_write_streamlit_upstream_state_sets_env_and_file(
    clean_upstream_env: None,
) -> None:
    path = write_streamlit_upstream_state("http://127.0.0.1:9999")
    try:
        assert path.is_file()
        assert path.read_text(encoding="utf-8").strip() == "http://127.0.0.1:9999"
        assert os.environ["FLUXLIT_STREAMLIT_UPSTREAM"] == "http://127.0.0.1:9999"
        assert os.environ[STREAMLIT_UPSTREAM_FILE_ENV] == str(path)
        assert read_streamlit_upstream_url() == "http://127.0.0.1:9999"
    finally:
        path.unlink(missing_ok=True)


def test_read_streamlit_upstream_prefers_file_over_conflicting_env(
    clean_upstream_env: None,
) -> None:
    path = write_streamlit_upstream_state("http://127.0.0.1:1111")
    try:
        os.environ["FLUXLIT_STREAMLIT_UPSTREAM"] = "http://127.0.0.1:2222"
        assert read_streamlit_upstream_url() == "http://127.0.0.1:1111"
    finally:
        path.unlink(missing_ok=True)


def test_read_streamlit_upstream_falls_back_when_file_unreadable(
    clean_upstream_env: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    missing = tmp_path / "gone.txt"
    monkeypatch.setenv(STREAMLIT_UPSTREAM_FILE_ENV, str(missing))
    monkeypatch.setenv("FLUXLIT_STREAMLIT_UPSTREAM", "http://127.0.0.1:3333")
    assert read_streamlit_upstream_url() == "http://127.0.0.1:3333"


def test_update_streamlit_upstream_file_rewrites_disk_and_env(
    clean_upstream_env: None,
) -> None:
    path = write_streamlit_upstream_state("http://127.0.0.1:4444")
    try:
        update_streamlit_upstream_file(path, "http://127.0.0.1:5555")
        assert path.read_text(encoding="utf-8").strip() == "http://127.0.0.1:5555"
        assert os.environ["FLUXLIT_STREAMLIT_UPSTREAM"] == "http://127.0.0.1:5555"
        assert read_streamlit_upstream_url() == "http://127.0.0.1:5555"
    finally:
        path.unlink(missing_ok=True)
