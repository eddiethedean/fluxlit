from __future__ import annotations

from pathlib import Path

import pytest

from fluxlit import FluxLit


def test_discover_pages_sorted_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pkg = tmp_path / "demo_pkg"
    (pkg / "pages").mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "pages" / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "pages" / "zoo.py").write_text(
        "def register(app):\n    @app.page('/zoo')\n    def zoo(st, client):\n        pass\n",
        encoding="utf-8",
    )
    (pkg / "pages" / "alpha.py").write_text(
        "def register(app):\n    @app.page('/alpha')\n    def alpha(st, client):\n        pass\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    app = FluxLit(title="Disc")
    app.discover_pages("pages", package="demo_pkg")
    paths = [p[0] for p in app.pages]
    assert paths == ["/alpha", "/zoo"]
