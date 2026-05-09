from __future__ import annotations

from fluxlit.page import PageFn


def test_pagefn_protocol_is_importable() -> None:
    """Importing :class:`PageFn` exercises the typing-only module body."""

    def render(st: object, client: object) -> None:
        del st, client

    fn: PageFn = render
    fn(object(), object())
