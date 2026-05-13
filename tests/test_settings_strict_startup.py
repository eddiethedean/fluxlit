"""Tests for ``FluxlitSettings.strict_startup``."""

from __future__ import annotations

import pytest

from fluxlit.config import FluxlitSettings


def test_strict_startup_accepts_minimal_defaults() -> None:
    FluxlitSettings(strict_startup=False)


def test_strict_startup_accepts_valid_proxy_combo() -> None:
    FluxlitSettings(
        strict_startup=True,
        trust_proxy=True,
        forwarded_allow_ips="127.0.0.1",
        gateway_max_proxy_request_body_bytes=65536,
        public_base_url="",
    )


def test_strict_startup_rejects_broad_forwarded_allow_ips() -> None:
    with pytest.raises(ValueError, match="strict_startup"):
        FluxlitSettings(
            strict_startup=True,
            trust_proxy=True,
            forwarded_allow_ips="*",
            gateway_max_proxy_request_body_bytes=1024,
        )


def test_strict_startup_rejects_unlimited_body_with_trust_proxy() -> None:
    with pytest.raises(ValueError, match="strict_startup"):
        FluxlitSettings(
            strict_startup=True,
            trust_proxy=True,
            forwarded_allow_ips="127.0.0.1",
            gateway_max_proxy_request_body_bytes=0,
        )


def test_strict_startup_rejects_subpath_without_public_base_url() -> None:
    with pytest.raises(ValueError, match="strict_startup"):
        FluxlitSettings(
            strict_startup=True,
            root_path="/apps/x",
            trust_proxy=True,
            forwarded_allow_ips="10.0.0.1",
            gateway_max_proxy_request_body_bytes=1024,
        )


def test_strict_startup_rejects_subpath_without_trust_proxy() -> None:
    with pytest.raises(ValueError, match="strict_startup"):
        FluxlitSettings(
            strict_startup=True,
            root_path="/apps/x",
            public_base_url="https://ex.example.com/apps/x",
            gateway_max_proxy_request_body_bytes=1024,
        )


def test_strict_startup_rejects_rejected_forward_header_names() -> None:
    with pytest.raises(ValueError, match="strict_startup"):
        FluxlitSettings(
            strict_startup=True,
            gateway_forward_client_headers_to_streamlit=["authorization"],
            gateway_max_proxy_request_body_bytes=1024,
        )


def test_strict_startup_rejects_public_base_url_path_mismatch() -> None:
    with pytest.raises(ValueError, match="strict_startup"):
        FluxlitSettings(
            strict_startup=True,
            root_path="/apps/demo",
            public_base_url="https://ex.example.com/wrong",
            trust_proxy=True,
            forwarded_allow_ips="127.0.0.1",
            gateway_max_proxy_request_body_bytes=1024,
        )
