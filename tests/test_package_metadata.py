from __future__ import annotations

from pathlib import Path

import fluxlit


def test_package_includes_pep561_marker() -> None:
    assert (Path(fluxlit.__file__).resolve().parent / "py.typed").is_file()
