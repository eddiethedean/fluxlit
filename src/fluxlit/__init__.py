"""FluxLit public API.

FluxLit unifies **FastAPI** and **Streamlit** behind one ASGI gateway: use
:class:`~fluxlit.app.FluxLit` for routes and pages, :class:`~fluxlit.client.ApiClient`
from Streamlit for server-side HTTP to your API, and :class:`~fluxlit.testing.FluxLitTestClient`
in tests.

The ``fluxlit`` console script (see :mod:`fluxlit.cli`) runs the combined dev/prod stack.

Optional auth ergonomics (after ``pip install "fluxlit[auth]"``):
:meth:`fluxlit.app.FluxLit.make_jwt_bearer`,
:meth:`fluxlit.app.FluxLit.attach_oidc_login`, and
:func:`fluxlit.streamlit_auth.prepare_streamlit_api_client` reduce boilerplate when using
``FLUXLIT_JWT_*`` and OIDC BFF env vars.
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
from fluxlit.streamlit_auth import (
    bearer_headers_from_session,
    exchange_auth_code_from_query,
    prepare_streamlit_api_client,
)
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
    "prepare_streamlit_api_client",
    "issue_hs256_access_token",
    "pkce_pair",
    "register_oidc_bff_routes",
    "__version__",
]
__version__ = "0.3.0"
