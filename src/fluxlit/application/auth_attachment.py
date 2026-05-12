"""OIDC BFF and JWT bearer wiring for :class:`~fluxlit.app.FluxLit`."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeAlias

from fastapi import APIRouter

from fluxlit.auth.jwt import JWTBearer
from fluxlit.auth.oidc import GenericOIDCClient, OIDCBFFConfig, register_oidc_bff_routes

if TYPE_CHECKING:
    from fluxlit.app import FluxLit

    FluxLitApp: TypeAlias = FluxLit[Any]


class AuthAttachment:
    """Collaborator for JWT and OIDC routes on the host :class:`~fluxlit.app.FluxLit`."""

    def __init__(self, app: FluxLitApp) -> None:
        self._fluxlit = app

    def make_jwt_bearer(self) -> JWTBearer:
        """JWT :class:`~fluxlit.auth.jwt.JWTBearer` from settings (``FLUXLIT_JWT_*``)."""
        return JWTBearer.from_fluxlit_settings(self._fluxlit.settings)

    def attach_oidc_login(
        self,
        oidc: GenericOIDCClient,
        *,
        first_party_secret: str | None = None,
        **bff_overrides: Any,
    ) -> APIRouter:
        """Register OIDC login / callback / token-exchange routes on ``api``."""
        if self._fluxlit._oidc_bff_attached:
            msg = "attach_oidc_login() was already called on this FluxLit instance"
            raise ValueError(msg)
        secret = (first_party_secret or self._fluxlit.settings.oidc_bff_secret or "").strip()
        if not secret:
            msg = (
                "OIDC BFF needs a signing secret: pass first_party_secret=... or set "
                "FLUXLIT_OIDC_BFF_SECRET on FluxlitSettings"
            )
            raise ValueError(msg)
        public_raw = bff_overrides.pop("public_base_url", None)
        if public_raw is not None:
            public_base = str(public_raw).strip()
        else:
            public_base = (self._fluxlit.settings.public_base_url or "").strip()
        cfg = OIDCBFFConfig(
            oidc=oidc,
            first_party_secret=secret,
            public_base_url=public_base,
            **bff_overrides,
        )
        router = register_oidc_bff_routes(self._fluxlit.api, cfg)
        self._fluxlit._oidc_bff_attached = True
        return router
