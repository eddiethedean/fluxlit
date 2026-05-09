from __future__ import annotations

from fluxlit import FluxLit


def test_page_registration() -> None:
    app = FluxLit(title="T")

    @app.page("/dash", title="Dash")
    def dash(st, client) -> None:  # noqa: ARG001
        pass

    paths = {p[0]: p[1] for p in app.pages}
    assert paths["/dash"] == "Dash"
