# Sphinx configuration for FluxLit. Builds on Read the Docs and locally via:
#   pip install -e ".[docs]"
#   sphinx-build -b html docs docs/_build/html
from __future__ import annotations

import os
import sys
from importlib import metadata

sys.path.insert(0, os.path.abspath("../src"))

project = "FluxLit"
copyright = "FluxLit contributors"
author = "FluxLit contributors"

try:
    version = metadata.version("fluxlit")
except metadata.PackageNotFoundError:
    version = "0.0.0"
release = version

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "sphinx_autodoc_typehints",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "furo"
html_title = f"{project} {version}"
html_static_path = ["_static"]

language = "en"

myst_enable_extensions = ["colon_fence", "deflist"]

autodoc_default_options = {
    "members": True,
    "show-inheritance": True,
    "undoc-members": False,
}
autodoc_typehints = "description"
autodoc_typehints_description_target = "documented"

autosummary_generate = True

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "fastapi": ("https://fastapi.tiangolo.com/", None),
    "starlette": ("https://www.starlette.io/", None),
    "pydantic": ("https://docs.pydantic.dev/latest/", None),
}

nitpick_ignore = [
    ("py:class", "typer.models.Context"),
    ("py:class", "typer.core.Typer"),
]

suppress_warnings = [
    "myst.xref_missing",
    "sphinx_autodoc_typehints.forward_reference",
]
