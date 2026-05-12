"""FastAPI-style dependency markers and resolution for Streamlit page handlers."""

from __future__ import annotations

import asyncio
import contextvars
import inspect
import json
import os
import threading
from collections.abc import Callable, Mapping
from typing import Annotated, Any, ForwardRef, get_args, get_origin, get_type_hints

from fluxlit.client import ApiClient
from fluxlit.config import FluxlitSettings
from fluxlit.url_session import SessionStore

_header_context: contextvars.ContextVar[Mapping[str, str] | None] = contextvars.ContextVar(
    "fluxlit_page_headers",
    default=None,
)


_HeaderCtxToken = contextvars.Token[Mapping[str, str] | None]


def set_page_header_context(headers: Mapping[str, str] | None) -> _HeaderCtxToken:
    """Set optional header map for :class:`Header` injection (tests or future gateway hook)."""
    return _header_context.set(headers)


def reset_page_header_context(token: _HeaderCtxToken) -> None:
    _header_context.reset(token)


class Depends:
    """Declare a page dependency callable ``( -> T)`` resolved before the handler runs."""

    def __init__(
        self,
        dependency: Callable[..., Any] | None = None,
        *,
        use_cache: bool = True,
    ) -> None:
        self.dependency = dependency
        self.use_cache = use_cache


class Header:
    """Inject a header value by name (from :func:`set_page_header_context` or *overrides*)."""

    def __init__(self, name: str) -> None:
        self.name = name.lower()


class Cookie:
    """Reserved for future cookie-based injection (same resolution path as :class:`Header`)."""

    def __init__(self, name: str) -> None:
        self.name = name.lower()


def env_page_overrides() -> dict[str, Any]:
    """Parse ``FLUXLIT_TEST_PAGE_OVERRIDES`` JSON (used by tests to inject deps)."""
    raw = os.environ.get("FLUXLIT_TEST_PAGE_OVERRIDES", "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return dict(data) if isinstance(data, dict) else {}


def _strip_annotated(tp: Any) -> Any:
    origin = get_origin(tp)
    if origin is Annotated:
        return get_args(tp)[0]
    return tp


def _unwrap_depends(param: inspect.Parameter, hints: dict[str, Any], name: str) -> Depends | None:
    ann = hints.get(name, param.annotation)
    if ann is inspect.Parameter.empty:
        ann = Any
    origin = get_origin(ann)
    if origin is Annotated:
        for meta in get_args(ann)[1:]:
            if isinstance(meta, Depends):
                return meta
    if isinstance(param.default, Depends):
        return param.default
    return None


def _unwrap_header(param: inspect.Parameter, hints: dict[str, Any], name: str) -> Header | None:
    ann = hints.get(name, param.annotation)
    origin = get_origin(ann)
    if origin is Annotated:
        for meta in get_args(ann)[1:]:
            if isinstance(meta, Header):
                return meta
    return None


def _unwrap_cookie(param: inspect.Parameter, hints: dict[str, Any], name: str) -> Cookie | None:
    ann = hints.get(name, param.annotation)
    origin = get_origin(ann)
    if origin is Annotated:
        for meta in get_args(ann)[1:]:
            if isinstance(meta, Cookie):
                return meta
    return None


def _call_kw_for_fn(fn: Callable[..., Any], kw: dict[str, Any]) -> dict[str, Any]:
    sig = inspect.signature(fn)
    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
        return dict(kw)
    return {k: v for k, v in kw.items() if k in sig.parameters}


def _header_from_streamlit_context(st: Any, name_lc: str) -> str | None:
    """Best-effort read from ``st.context.headers`` (Streamlit 1.30+)."""
    try:
        proxy = getattr(st, "context", None)
        headers = getattr(proxy, "headers", None) if proxy is not None else None
        if headers is None:
            return None
        get = getattr(headers, "get", None)
        if get is None:
            return None
        v = get(name_lc)
        if v is not None:
            return str(v)
        items = getattr(headers, "items", None)
        if callable(items):
            for k, val in items():
                if str(k).lower() == name_lc:
                    return str(val)
    except Exception:
        return None
    return None


def _resolve_depends_callable(dependency: Callable[..., Any], *, app: Any) -> Any:
    allow_async = bool(getattr(app.settings, "async_page_depends", False))

    def _run_coro_no_loop(coro: Any) -> Any:
        import anyio

        async def _await() -> Any:
            return await coro

        return anyio.run(_await)

    def _run_coro_isolated_thread(coro: Any) -> Any:
        """Run *coro* on a fresh event loop in a short-lived daemon thread.

        Avoids ``RuntimeError`` when Streamlit (or another caller) already has a running
        loop on this thread while ``anyio.run`` / ``asyncio.run`` cannot nest.
        """
        result: list[Any] = []
        error: list[BaseException] = []

        def _worker() -> None:
            try:

                async def _await_one() -> Any:
                    return await coro

                result.append(asyncio.run(_await_one()))
            except BaseException as exc:  # noqa: BLE001 — propagate dependency failures
                error.append(exc)

        th = threading.Thread(target=_worker, name="fluxlit-async-dep", daemon=True)
        th.start()
        th.join(timeout=300.0)
        if th.is_alive():
            msg = "async Depends resolution timed out"
            raise TimeoutError(msg)
        if error:
            raise error[0]
        return result[0]

    def _await_async_dep(coro: Any) -> Any:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return _run_coro_no_loop(coro)
        return _run_coro_isolated_thread(coro)

    if inspect.iscoroutinefunction(dependency):
        if not allow_async:
            msg = (
                f"Depends({dependency!r}) is async; set FLUXLIT_ASYNC_PAGE_DEPENDS=1 "
                "or use a synchronous callable."
            )
            raise TypeError(msg)
        return _await_async_dep(dependency())
    out = dependency()
    if inspect.iscoroutine(out):
        if not allow_async:
            msg = (
                "Depends(...) returned a coroutine; set FLUXLIT_ASYNC_PAGE_DEPENDS=1 "
                "or return a plain value from the dependency."
            )
            raise TypeError(msg)
        return _await_async_dep(out)
    return out


def resolve_page_kwargs(
    fn: Callable[..., Any],
    *,
    st: Any,
    client: ApiClient,
    app: Any,
    overrides: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build kwargs for *fn* (``st``, ``client``, typed injections, ``Depends``)."""
    from fluxlit.application.public_urls import FluxLitPublicUrls

    merged = {**env_page_overrides(), **dict(overrides or {})}
    sig = inspect.signature(fn)
    globalns = getattr(fn, "__globals__", None) or {}
    hints = get_type_hints(fn, globalns=globalns, include_extras=True)
    kwargs: dict[str, Any] = {}
    for name, param in sig.parameters.items():
        dep = _unwrap_depends(param, hints, name)
        if dep is not None and dep.dependency is not None:
            kwargs[name] = _resolve_depends_callable(dep.dependency, app=app)
            continue
        hdr = _unwrap_header(param, hints, name)
        if hdr is not None:
            if name in merged:
                kwargs[name] = merged[name]
            else:
                ctx = _header_context.get() or {}
                val = ctx.get(hdr.name)
                if val is None:
                    val = _header_from_streamlit_context(st, hdr.name)
                kwargs[name] = val
            continue
        ck = _unwrap_cookie(param, hints, name)
        if ck is not None:
            kwargs[name] = merged.get(name)
            continue
        if name == "st":
            kwargs[name] = st
            continue
        if name == "client":
            kwargs[name] = client
            continue
        ann = hints.get(name, param.annotation)
        base = _strip_annotated(ann)
        if base is inspect.Parameter.empty:
            base = Any  # pragma: no cover
        if isinstance(base, ForwardRef):  # pragma: no cover
            base = base._evaluate(globalns, globalns, frozenset())  # noqa: SLF001
        if base is Any:  # pragma: no cover
            continue
        try:
            if issubclass(base, FluxlitSettings):
                kwargs[name] = app.settings
                continue
        except TypeError:
            pass
        try:
            if issubclass(base, FluxLitPublicUrls):
                kwargs[name] = app.urls
                continue
        except TypeError:
            pass
        try:
            from fluxlit.app import FluxLit as FluxLitCls

            if issubclass(base, FluxLitCls):
                kwargs[name] = app
                continue
        except TypeError:
            pass
        if base is ApiClient or (isinstance(base, type) and issubclass(base, ApiClient)):
            kwargs[name] = client
            continue
        store = getattr(app, "session_store", None)
        if store is not None and base is SessionStore:
            kwargs[name] = store
            continue
        from fluxlit.pages.flags import FluxlitFeatureFlags

        if base is FluxlitFeatureFlags:
            kwargs[name] = FluxlitFeatureFlags.from_environ()
            continue
    return kwargs


def resolve_and_call_page(
    rec: Any,
    st: Any,
    client: ApiClient,
    app: Any,
    overrides: Mapping[str, Any] | None,
) -> Any:
    """Resolve kwargs, call handler, apply returned :class:`~fluxlit.pages.meta.PageMeta`."""
    from fluxlit.pages.apply_meta import apply_returned_page_meta, coerce_page_return
    from fluxlit.pages.flags import FluxlitFeatureFlags
    from fluxlit.pages.records import PageRecord

    if not isinstance(rec, PageRecord):
        msg = "resolve_and_call_page expects PageRecord"
        raise TypeError(msg)
    merged_overrides: dict[str, Any] = {**env_page_overrides(), **dict(overrides or {})}
    kw = resolve_page_kwargs(rec.fn, st=st, client=client, app=app, overrides=merged_overrides)
    call_kw = _call_kw_for_fn(rec.fn, kw)
    fn = rec.fn
    flags = FluxlitFeatureFlags.from_environ()
    yield_pages = flags.experimental_yield_pages or bool(
        getattr(app.settings, "experimental_yield_pages", False)
    )
    if yield_pages and inspect.isgeneratorfunction(fn):
        gen = fn(**call_kw)
        try:
            first = next(gen)
        except StopIteration:
            return None
        apply_returned_page_meta(st, coerce_page_return(st, first))
        try:
            second = next(gen)
        except StopIteration:
            return first
        apply_returned_page_meta(st, coerce_page_return(st, second))
        return second
    out = fn(**call_kw)
    meta = coerce_page_return(st, out)
    apply_returned_page_meta(st, meta)
    return out


__all__ = [
    "Cookie",
    "Depends",
    "Header",
    "env_page_overrides",
    "reset_page_header_context",
    "resolve_and_call_page",
    "resolve_page_kwargs",
    "set_page_header_context",
]
