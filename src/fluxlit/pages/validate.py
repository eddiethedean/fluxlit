"""Validate registered Streamlit pages and manifest JSON (CLI / CI)."""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from fluxlit.app import FluxLit
from fluxlit.pages.manifest import build_page_manifest
from fluxlit.pages.signature import validate_strict_page_signature
from fluxlit.pages.slug import page_slug


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
    Checks for duplicate page paths and for distinct paths that share the same
    ``url_path`` slug (after leading/trailing slash normalization).
    Always verifies :func:`~fluxlit.pages.manifest.build_page_manifest` is JSON-serializable.
    """
    errors: list[str] = []
    recs = app.page_records
    path_counts: dict[str, int] = {}
    for rec in recs:
        path_counts[rec.path] = path_counts.get(rec.path, 0) + 1
    for path, n in sorted(path_counts.items()):
        if n > 1:
            errors.append(f"duplicate page path {path!r} ({n} registrations)")
    slug_paths: dict[str, set[str]] = defaultdict(set)
    for rec in recs:
        slug_paths[page_slug(rec.path)].add(rec.path)
    for slug, paths in sorted(slug_paths.items()):
        if len(paths) > 1:
            plist = ", ".join(sorted(repr(p) for p in paths))
            errors.append(f"pages {plist} all map to url_path slug {slug!r}")
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
