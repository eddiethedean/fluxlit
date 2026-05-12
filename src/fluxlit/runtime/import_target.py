"""Resolve ``module:attr`` targets and load :class:`~fluxlit.app.FluxLit` instances."""

from __future__ import annotations

import importlib
import importlib.util
import ipaddress
import os
import socket
import sys
import urllib.parse
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fluxlit.api_mount import normalize_api_mount_path

if TYPE_CHECKING:
    from fluxlit.app import FluxLit


def find_free_port() -> int:
    """Bind to ``127.0.0.1:0`` and return the assigned ephemeral port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _loopback_http_host_for_client(bind_host: str) -> str:
    """Host segment for URLs used from the Streamlit subprocess to reach the gateway.

    ``0.0.0.0`` / empty bind addresses are valid for listening but invalid as HTTP
    client targets; use loopback. IPv6 literals are bracketed for RFC 3986 URLs.
    """
    h = bind_host.strip()
    if h in {"", "0.0.0.0"}:
        return "127.0.0.1"
    bare = h[1:-1] if h.startswith("[") and h.endswith("]") else h
    try:
        addr = ipaddress.ip_address(bare)
    except ValueError:
        return h
    if addr.is_unspecified:
        return "127.0.0.1"
    if isinstance(addr, ipaddress.IPv6Address):
        return f"[{addr}]"
    return str(addr)


def internal_api_base_url(*, bind_host: str, port: int, api_mount_path: str) -> str:
    """Build ``FLUXLIT_INTERNAL_API_BASE`` for the Streamlit child (same machine as gateway).

    ``bind_host`` is the Uvicorn bind address; the URL uses a loopback-safe host when
    needed so :class:`~fluxlit.client.ApiClient` can connect from the sidecar process.
    """
    path = normalize_api_mount_path(api_mount_path)
    netloc = f"{_loopback_http_host_for_client(bind_host)}:{port}"
    return urllib.parse.urlunparse(("http", netloc, path, "", "", ""))


def _fluxlit_import_hint(target: str, mod_name: str) -> str:
    return (
        f"Cannot import module {mod_name!r} for FluxLit target {target!r}. "
        "Put the package on PYTHONPATH (for example `export PYTHONPATH=$(pwd)` before "
        "`fluxlit dev`). Tip: if you have a local `app.py`, FluxLit prefers it for "
        "`app:app`; you can also use an explicit file target like `./app.py:app`."
    )


def _prepend_module_dir(path: Path) -> None:
    module_dir = str(path.parent.resolve())
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)


def import_target_candidates(mod_name: str, *, paths: Sequence[str] | None = None) -> list[Path]:
    """Return importable file/package candidates for a top-level target module.

    This is intentionally conservative: dotted package paths and explicit file targets
    are skipped because their resolution rules are more specific than the common
    monorepo footgun of several top-level ``app`` or ``main`` modules on ``sys.path``.
    """
    if not mod_name or "." in mod_name:
        return []
    if Path(mod_name).suffix == ".py" or any(sep in mod_name for sep in (os.sep, os.altsep) if sep):
        return []

    found: list[Path] = []
    seen: set[Path] = set()
    for raw in sys.path if paths is None else paths:
        base = Path(raw or ".")
        for candidate in (base / f"{mod_name}.py", base / mod_name / "__init__.py"):
            if not candidate.is_file():
                continue
            try:
                resolved = candidate.resolve()
            except OSError:
                continue
            if resolved in seen:
                continue
            seen.add(resolved)
            found.append(resolved)
    return found


def _import_target_module(mod_name: str) -> object:
    """Import a target module, preferring local ``<cwd>/<mod_name>.py`` when present.

    This avoids a common footgun where users accidentally add ``.../fluxlit/src/fluxlit`` to
    ``PYTHONPATH`` (or similar), making FluxLit's own ``app.py`` importable as top-level
    ``import app`` and breaking ``app:app`` targets.
    """

    def _reuse_loaded(sys_mod_name: str, file_path: Path) -> object | None:
        existing = sys.modules.get(sys_mod_name)
        if existing is None:
            return None
        ef = getattr(existing, "__file__", None)
        if ef is None:
            return None
        try:
            if Path(ef).resolve() == file_path.resolve():
                return existing
        except OSError:
            return None
        return None

    # Accept explicit file targets like "./app.py" or "/abs/path/app.py".
    p = Path(mod_name)
    if p.suffix == ".py" or any(sep in mod_name for sep in (os.sep, os.altsep) if sep):
        path = p if p.is_absolute() else (Path.cwd() / p)
        if not path.is_file():
            raise ModuleNotFoundError(mod_name)
        stem = p.stem
        reused = _reuse_loaded(stem, path)
        if reused is not None:
            return reused
        spec = importlib.util.spec_from_file_location(stem, path)
        if spec is None or spec.loader is None:
            raise ModuleNotFoundError(mod_name)
        module = importlib.util.module_from_spec(spec)
        # Ensure future imports of the stem see this module.
        sys.modules[stem] = module
        _prepend_module_dir(path)
        spec.loader.exec_module(module)
        return module

    # Prefer a local "<cwd>/<name>.py" file over sys.path resolution.
    # This makes "fluxlit dev app:app" robust even if PYTHONPATH is polluted.
    local = Path.cwd() / f"{mod_name}.py"
    if mod_name and "." not in mod_name and local.is_file():
        reused = _reuse_loaded(mod_name, local)
        if reused is not None:
            return reused
        spec = importlib.util.spec_from_file_location(mod_name, local)
        if spec is None or spec.loader is None:
            raise ModuleNotFoundError(mod_name)
        module = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = module
        _prepend_module_dir(local)
        spec.loader.exec_module(module)
        return module

    return importlib.import_module(mod_name)


def load_fluxlit(target: str) -> FluxLit[Any]:
    """Import ``module:attribute`` and ensure the object is a :class:`~fluxlit.app.FluxLit`.

    Raises:
        ValueError: If ``target`` is not a ``module:attr`` string.
        ModuleNotFoundError: If ``module`` cannot be imported (message includes a short hint).
        AttributeError: If ``module`` has no such attribute.
        TypeError: If ``attr`` is not a :class:`~fluxlit.app.FluxLit` instance.
    """
    from fluxlit.app import FluxLit as FluxLitCls

    mod_name, sep, attr = target.partition(":")
    if not sep or not attr:
        msg = "App target must look like 'my_module:app'"
        raise ValueError(msg)
    try:
        module = _import_target_module(mod_name)
    except ModuleNotFoundError as e:
        raise ModuleNotFoundError(_fluxlit_import_hint(target, mod_name)) from e
    try:
        obj = getattr(module, attr)
    except AttributeError as e:
        raise AttributeError(
            f"Module {mod_name!r} has no attribute {attr!r} (FluxLit target {target!r})."
        ) from e
    if not isinstance(obj, FluxLitCls):
        raise TypeError(f"{target} must resolve to a FluxLit instance, not {type(obj).__name__!r}")
    return obj
