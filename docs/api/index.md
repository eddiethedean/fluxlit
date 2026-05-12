# Python API reference

Generated from docstrings with Sphinx autodoc. Public modules:

```{eval-rst}
.. automodule:: fluxlit
   :members:
   :exclude-members: ApiClient, FluxLit, FluxlitSettings, FluxLitTestClient, GenericOIDCClient, GenericOIDCClientConfig, OIDCBFFConfig, OIDCProvider, JWTAuthConfig, JWTBearer, RequireRoles, RequireScopes, StandardClaims, issue_hs256_access_token, pkce_pair, register_oidc_bff_routes, bearer_headers_from_session, exchange_auth_code_from_query, prepare_streamlit_api_client, match_nav_page, query_params
   :show-inheritance:

.. automodule:: fluxlit.app
   :members:
   :show-inheritance:

.. automodule:: fluxlit.client
   :members:
   :show-inheritance:

.. automodule:: fluxlit.config
   :members:
   :show-inheritance:

.. automodule:: fluxlit.config.project
   :members:
   :show-inheritance:

.. automodule:: fluxlit.logging
   :members:
   :show-inheritance:

.. automodule:: fluxlit.gateway
   :members:
   :show-inheritance:

.. automodule:: fluxlit.health
   :members:
   :show-inheritance:

.. automodule:: fluxlit.logging.redact
   :members:
   :show-inheritance:

.. automodule:: fluxlit.runtime
   :members:
   :show-inheritance:

.. automodule:: fluxlit.testing
   :members:
   :show-inheritance:

.. automodule:: fluxlit.tracing
   :members:
   :show-inheritance:

.. automodule:: fluxlit.api
   :members:
   :show-inheritance:

.. automodule:: fluxlit.auth
   :members:
   :show-inheritance:

.. automodule:: fluxlit.auth.jwt
   :members:
   :show-inheritance:

.. automodule:: fluxlit.auth.oidc
   :members:
   :show-inheritance:

.. automodule:: fluxlit.auth.streamlit
   :members:
   :show-inheritance:

.. automodule:: fluxlit.url_session
   :members:
   :show-inheritance:

.. automodule:: fluxlit.deep_links
   :members:
   :show-inheritance:

.. automodule:: fluxlit.security
   :members:
   :show-inheritance:

.. automodule:: fluxlit.streamlit.page
   :members:
   :show-inheritance:
```

The Typer CLI module ({mod}`fluxlit.cli`) is primarily used via the `fluxlit` console script; its objects are listed below for completeness.

```{eval-rst}
.. automodule:: fluxlit.cli
   :members:
   :show-inheritance:
```

The Streamlit entry script **`fluxlit.streamlit.main`** is executed by `streamlit run` with `FLUXLIT_APP` set. It is not import-safe for autodoc (module-level initialization). See the source file `streamlit/main.py` in the repository.
