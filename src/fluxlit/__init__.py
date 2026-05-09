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
from fluxlit.jwt_auth import (
    JWTAuthConfig,
    JWTBearer,
    RequireRoles,
    RequireScopes,
    StandardClaims,
    issue_hs256_access_token,
)
from fluxlit.oidc import (
    GenericOIDCClient,
    GenericOIDCClientConfig,
    OIDCBFFConfig,
    OIDCProvider,
    pkce_pair,
    register_oidc_bff_routes,
)
from fluxlit.streamlit_auth import bearer_headers_from_session, exchange_auth_code_from_query
from fluxlit.testing import FluxLitTestClient

__all__ = [
    "ApiClient",
    "FluxLitTestClient",
    "FluxlitSettings",
    "FluxLit",
    "JWTAuthConfig",
    "JWTBearer",
    "OIDCBFFConfig",
    "OIDCProvider",
    "GenericOIDCClient",
    "GenericOIDCClientConfig",
    "RequireRoles",
    "RequireScopes",
    "StandardClaims",
    "bearer_headers_from_session",
    "exchange_auth_code_from_query",
    "issue_hs256_access_token",
    "pkce_pair",
    "register_oidc_bff_routes",
    "__version__",
]
__version__ = "0.2.0"
