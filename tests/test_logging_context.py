from __future__ import annotations

from fluxlit.logging_context import (
    get_request_id,
    new_request_id,
    reset_request_id,
    set_request_id,
)


def test_set_get_reset_request_id() -> None:
    assert get_request_id() is None
    tok = set_request_id("rid-1")
    assert get_request_id() == "rid-1"
    reset_request_id(tok)
    assert get_request_id() is None


def test_new_request_id_is_uuid_like() -> None:
    rid = new_request_id()
    assert len(rid) == 36
    assert rid.count("-") == 4
