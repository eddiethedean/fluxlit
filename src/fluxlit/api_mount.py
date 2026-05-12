"""Normalize the public API URL mount path (no gateway imports — safe for settings)."""


def normalize_api_mount_path(api_mount_path: str) -> str:
    """Normalize the public API URL prefix for gateway dispatch and URL helpers.

    Ensures a single leading ``/`` and no trailing slash (except the root ``"/"``).
    Empty or whitespace-only values fall back to ``"/api"``.
    """
    p = (api_mount_path or "/api").strip()
    if not p.startswith("/"):
        p = f"/{p}"
    return p.rstrip("/") or "/"
