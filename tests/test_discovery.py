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


def test_discover_pages_skips_private_modules_packages_and_missing_register(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pkg = tmp_path / "mixed_pkg"
    pages = pkg / "pages"
    pages.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pages / "__init__.py").write_text("", encoding="utf-8")
    (pages / "_private.py").write_text(
        "raise RuntimeError('should not import')\n", encoding="utf-8"
    )
    (pages / "no_register.py").write_text("VALUE = 1\n", encoding="utf-8")
    (pages / "registered.py").write_text(
        "def register(app):\n"
        "    @app.page('/registered')\n"
        "    def page(st, client):\n"
        "        pass\n",
        encoding="utf-8",
    )
    (pages / "nested").mkdir()
    (pages / "nested" / "__init__.py").write_text("", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))

    app = FluxLit(title="Mixed")
    app.discover_pages("pages", package="mixed_pkg")
    assert [p[0] for p in app.pages] == ["/registered"]


def test_page_decorator_uses_generic_title_for_callable_object() -> None:
    class CallablePage:
        def __call__(self, st, client) -> None:
            pass

    app = FluxLit(title="Callable")
    app.page("/callable")(CallablePage())
    assert app.pages[0][1] == "Page"
