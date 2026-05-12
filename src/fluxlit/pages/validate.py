"""Validate registered Streamlit pages and manifest JSON (CLI / CI)."""

from __future__ import annotations

import json
from typing import Any

from fluxlit.app import FluxLit
from fluxlit.pages.manifest import build_page_manifest
from fluxlit.pages.signature import validate_strict_page_signature


def validate_fluxlit_pages(
    app: FluxLit[Any],
    *,
    strict_signatures: bool | None = None,
) -> list[str]:
    """Return human-readable errors, or an empty list when checks pass.

    When *strict_signatures* is ``None``, uses
    :attr:`~fluxlit.config.FluxlitSettings.strict_page_signatures`.
    When true, runs :func:`~fluxlit.pages.signature.validate_strict_page_signature` on each
    page handler.
    Always verifies :func:`~fluxlit.pages.manifest.build_page_manifest` is JSON-serializable.
    """
    errors: list[str] = []
    do_strict = (
        app.settings.strict_page_signatures if strict_signatures is None else strict_signatures
    )
    if do_strict:
        for rec in app.page_records:
            try:
                validate_strict_page_signature(rec.fn)
            except TypeError as e:
                errors.append(f"{rec.path}: {e}")
    try:
        json.dumps(build_page_manifest(app))
    except (TypeError, ValueError) as e:
        errors.append(f"manifest JSON: {e}")
    return errors


__all__ = ["validate_fluxlit_pages"]
