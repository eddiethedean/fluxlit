"""Typed helpers for ``st.session_state`` backed by Pydantic models."""

from __future__ import annotations

from typing import Any, Literal, TypeVar

from pydantic import BaseModel, ValidationError

ModelT = TypeVar("ModelT", bound=BaseModel)


class SessionModel:
    """Read/write a Pydantic model to Streamlit session state keys matching field names."""

    def __init__(self, st: Any, *, extra: Literal["ignore", "forbid"] = "ignore") -> None:
        self._st = st
        self._extra = extra

    def read_into(self, model_type: type[ModelT]) -> ModelT:
        """Build *model_type* from ``st.session_state`` (missing keys use defaults)."""
        ss = getattr(self._st, "session_state", {})
        data: dict[str, Any] = {}
        for name in model_type.model_fields:
            if hasattr(ss, "__contains__") and name in ss:
                data[name] = ss[name]
        try:
            return model_type.model_validate(data)
        except ValidationError:
            raise

    def write_from(self, model: BaseModel) -> None:
        """Write ``model.model_dump()`` into ``st.session_state``."""
        ss = self._st.session_state
        payload = model.model_dump()
        allowed = set(model.__class__.model_fields)
        if self._extra == "forbid":
            bad = set(payload) - allowed
            if bad:
                msg = f"Unexpected session keys: {sorted(bad)}"
                raise ValueError(msg)
        for k, v in payload.items():
            ss[k] = v


__all__ = ["SessionModel"]
