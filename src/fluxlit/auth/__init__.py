"""Authentication helpers (JWT, OIDC BFF, Streamlit-side helpers, trusted proxy headers)."""

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
from fluxlit.auth.trusted_proxy import (
    AuthDependency,
    TrustedProxyUser,
    TrustedProxyUserConfig,
    proxy_user_header,
)

__all__ = [
    "AuthDependency",
    "GenericOIDCClient",
    "GenericOIDCClientConfig",
    "JWTAuthConfig",
    "JWTBearer",
    "OIDCBFFConfig",
    "OIDCProvider",
    "RequireRoles",
    "RequireScopes",
    "StandardClaims",
    "TrustedProxyUser",
    "TrustedProxyUserConfig",
    "bearer_headers_from_session",
    "exchange_auth_code_from_query",
    "issue_hs256_access_token",
    "pkce_pair",
    "prepare_streamlit_api_client",
    "proxy_user_header",
    "register_oidc_bff_routes",
]
