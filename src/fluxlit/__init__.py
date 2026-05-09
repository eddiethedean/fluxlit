"""FluxLit public API.

FluxLit unifies **FastAPI** and **Streamlit** behind one ASGI gateway: use
:class:`~fluxlit.app.FluxLit` for routes and pages, :class:`~fluxlit.client.ApiClient`
from Streamlit for server-side HTTP to your API, and :class:`~fluxlit.testing.FluxLitTestClient`
in tests.

The ``fluxlit`` console script (see :mod:`fluxlit.cli`) runs the combined dev/prod stack.
"""

from fluxlit.app import FluxLit
from fluxlit.client import ApiClient
from fluxlit.config import FluxlitSettings
from fluxlit.testing import FluxLitTestClient

__all__ = ["ApiClient", "FluxLitTestClient", "FluxlitSettings", "FluxLit", "__version__"]
__version__ = "0.2.0"
