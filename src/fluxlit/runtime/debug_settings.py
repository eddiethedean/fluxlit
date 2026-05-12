"""Merge diagnostic defaults when :attr:`~fluxlit.config.FluxlitSettings.debug` is enabled."""

from __future__ import annotations

from fluxlit.config import FluxlitSettings


def merge_debug_settings(settings: FluxlitSettings) -> FluxlitSettings:
    """Return *settings* with gateway/API logging defaults when ``debug`` is true.

    Idempotent: leaves explicit non-default ``log_level`` values unchanged and does not
    toggle logging flags that are already enabled.
    """
    if not settings.debug:
        return settings
    need_log = not settings.enable_gateway_access_log
    need_req = not settings.enable_request_logging
    need_lv = (settings.log_level or "").strip().lower() == "info"
    if not (need_log or need_req or need_lv):
        return settings
    updates: dict[str, object] = {}
    if need_log:
        updates["enable_gateway_access_log"] = True
    if need_req:
        updates["enable_request_logging"] = True
    if need_lv:
        updates["log_level"] = "debug"
    return settings.model_copy(update=updates)
