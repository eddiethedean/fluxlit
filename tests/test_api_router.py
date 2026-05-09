from __future__ import annotations

from enum import Enum

from fastapi import APIRouter

from fluxlit.api import router


class _Tag(Enum):
    users = "users"


def test_router_default_prefix_and_no_tags() -> None:
    r = router()
    assert isinstance(r, APIRouter)
    assert r.prefix == ""


def test_router_prefix_and_string_tags() -> None:
    r = router(prefix="/v1", tags=["a", "b"])
    assert r.prefix == "/v1"
    assert r.tags == ["a", "b"]


def test_router_accepts_string_tags_from_enum_values() -> None:
    r = router(tags=[_Tag.users.value])
    assert r.tags == ["users"]
