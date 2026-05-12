"""Typed query string parsing for Streamlit pages (Pydantic)."""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel, TypeAdapter, ValidationError

ModelT = TypeVar("ModelT", bound=BaseModel)


class Query:
    """Optional metadata for a query-shaped parameter (manifest / docs)."""

    def __init__(self, *, description: str = "") -> None:
        self.description = description


def _query_dict_from_st(st: Any) -> dict[str, Any]:
    qp = getattr(st, "query_params", None)
    if qp is None:
        return {}
    out: dict[str, Any] = {}
    try:
        keys = list(qp.keys())
    except Exception:  # noqa: BLE001
        return {}
    for k in keys:
        key = str(k)
        try:
            raw = qp.get(key) if hasattr(qp, "get") else qp[key]
        except Exception:  # noqa: BLE001
            continue
        if isinstance(raw, list):
            out[key] = raw[0] if len(raw) == 1 else raw
        else:
            out[key] = raw
    return out


def parse_query_params(
    st: Any,
    model: type[ModelT],
    *,
    strict: bool = False,
) -> ModelT:
    """Build *model* from ``st.query_params`` (list values → last kept for multi-value keys).

    On :class:`pydantic.ValidationError`, calls ``st.error`` with a short message unless
    *strict* is true, in which case the exception is re-raised.
    """
    raw = _query_dict_from_st(st)
    try:
        return model.model_validate(raw)
    except ValidationError as e:
        if strict:
            raise
        err = getattr(st, "error", None)
        if callable(err):
            err(f"Invalid query parameters: {e}")
        try:
            return model.model_validate({})
        except ValidationError:
            raise


def parse_query_params_adapter(
    st: Any,
    adapter: TypeAdapter[Any],
    *,
    strict: bool = False,
) -> Any:
    """Validate query params with a :class:`pydantic.TypeAdapter` (e.g. ``TypedDict``)."""
    raw = _query_dict_from_st(st)
    try:
        return adapter.validate_python(raw)
    except ValidationError as e:
        if strict:
            raise
        err = getattr(st, "error", None)
        if callable(err):
            err(f"Invalid query parameters: {e}")
        raise


def query_dict_for_manifest(st: Any) -> dict[str, Any]:
    """Return a JSON-friendly snapshot of current query keys (for manifest tooling)."""
    return dict(_query_dict_from_st(st))


__all__ = ["Query", "parse_query_params", "parse_query_params_adapter", "query_dict_for_manifest"]
