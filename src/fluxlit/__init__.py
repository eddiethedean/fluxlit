"""FluxLit public API.

FluxLit unifies **FastAPI** and **Streamlit** behind one ASGI gateway: use
:class:`~fluxlit.app.FluxLit` for routes and pages, :class:`~fluxlit.client.ApiClient`
from Streamlit for server-side HTTP to your API, and :class:`~fluxlit.testing.FluxLitTestClient`
in tests.

The ``fluxlit`` console script (see :mod:`fluxlit.cli`) runs the combined dev/prod stack.

Optional auth ergonomics (after ``pip install "fluxlit[auth]"``):
:meth:`fluxlit.app.FluxLit.make_jwt_bearer`,
:meth:`fluxlit.app.FluxLit.attach_oidc_login`, and
:func:`fluxlit.auth.prepare_streamlit_api_client` reduce boilerplate when using
``FLUXLIT_JWT_*`` and OIDC BFF env vars.
"""

from fluxlit.app import FluxLit
from fluxlit.application.public_urls import FluxLitPublicUrls
from fluxlit.auth.jwt import (
    JWTAuthConfig,
    JWTBearer,
    RequireRoles,
    RequireScopes,
    StandardClaims,
    issue_hs256_access_token,
)
from fluxlit.auth.oidc import (
    GenericOIDCClient,
    GenericOIDCClientConfig,
    OIDCBFFConfig,
    OIDCProvider,
    pkce_pair,
    register_oidc_bff_routes,
)
from fluxlit.auth.streamlit import (
    bearer_headers_from_session,
    exchange_auth_code_from_query,
    prepare_streamlit_api_client,
)
from fluxlit.client import ApiClient
from fluxlit.config import FluxlitSettings
from fluxlit.deep_links import match_nav_page, query_params
from fluxlit.testing import FluxLitTestClient, streamlit_main_path
from fluxlit.tracing import reset_trace_hook, set_trace_hook, trace_span
from fluxlit.url_session import (
    InMemorySessionStore,
    SessionStore,
    ensure_url_session,
    hydrate_url_session,
    new_session_id,
    persist_url_session,
)

__all__ = [
    "ApiClient",
    "FluxLitTestClient",
    "FluxlitSettings",
    "FluxLit",
    "FluxLitPublicUrls",
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
    "SessionStore",
    "InMemorySessionStore",
    "match_nav_page",
    "new_session_id",
    "ensure_url_session",
    "hydrate_url_session",
    "persist_url_session",
    "query_params",
    "reset_trace_hook",
    "set_trace_hook",
    "streamlit_main_path",
    "trace_span",
    "__version__",
]
__version__ = "0.8.0"
