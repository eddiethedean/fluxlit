"""Deep links to Streamlit pages: normalized query params and optional ``?page=`` routing."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Any, cast

from fluxlit.pages.records import PageRecord
from fluxlit.pages.slug import page_slug
from fluxlit.runtime.env_parse import truthy_env

_log = logging.getLogger(__name__)


def _scalar_query_value(raw: Any) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, list):
        return str(raw[0]) if raw else None
    return str(raw)


def query_params(st: Any) -> dict[str, str]:
    """Return the current URL query as plain ``str`` values (first value if a list).

    Streamlit (and ``AppTest``) may expose ``st.query_params`` values as strings or
    lists when multiple values share a key. This helper normalizes to a single
    ``str`` per key so page logic and email-link prefill stay simple.

    Missing or unreadable ``query_params`` yields an empty dict.
    """
    qp = getattr(st, "query_params", None)
    if qp is None:
        return {}
    keys: list[str]
    try:
        keys = [str(k) for k in qp.keys()]
    except Exception as exc:  # noqa: BLE001 — best-effort for mocks / older Streamlit
        if truthy_env("FLUXLIT_DEBUG"):
            _log.debug(
                "query_params: could not list keys from st.query_params: %s", exc, exc_info=True
            )
        if isinstance(qp, dict):
            keys = [str(k) for k in qp]
        else:
            return {}
    out: dict[str, str] = {}
    for k in keys:
        try:
            raw = qp.get(k) if hasattr(qp, "get") else qp[k]
        except Exception as exc:  # noqa: BLE001
            if truthy_env("FLUXLIT_DEBUG"):
                _log.debug(
                    "query_params: could not read key %r from st.query_params: %s",
                    k,
                    exc,
                    exc_info=True,
                )
            continue
        v = _scalar_query_value(raw)
        if v is not None:
            out[k] = v
    return out


def match_nav_page(
    params: Mapping[str, str],
    pages: Sequence[tuple[str, str] | tuple[str, str, Any] | Any],
    *,
    page_key: str = "page",
) -> tuple[str, str] | None:
    """Resolve ``(path, title)`` from a ``page``-style query key and registered pages.

    Compares the ``page_key`` value (default ``\"page\"``) to each page **title**,
    **path**, and Streamlit-style **slug** (``\"/\"`` → ``\"home\"``; otherwise the
    path without slashes). The first match in *pages* wins (order matches
    :attr:`~fluxlit.app.FluxLit.pages`).

    Returns ``None`` when the key is missing, empty, or unmatched.
    """
    wanted = (params.get(page_key) or "").strip()
    if not wanted:
        return None
    for row in pages:
        if isinstance(row, PageRecord):
            path, title = row.path, row.title
        elif hasattr(row, "path") and hasattr(row, "title"):
            duck = cast(Any, row)
            path, title = str(duck.path), str(duck.title)
        else:
            path, title = row[0], row[1]
        slug = page_slug(path)
        if wanted == title or wanted == path or wanted == slug:
            return (path, title)
        w = wanted.strip("/")
        p = path.strip("/")
        if w and p and w == p:
            return (path, title)
    return None


__all__ = ["match_nav_page", "query_params"]
