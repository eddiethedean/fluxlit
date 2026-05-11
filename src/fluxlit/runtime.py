"""Process orchestration: load ``FluxLit`` by import path, spawn Streamlit, run Uvicorn."""

from __future__ import annotations

import contextlib
import importlib
import ipaddress
import os
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import uvicorn
from starlette.types import ASGIApp, Receive, Scope, Send

from fluxlit.gateway import build_gateway, normalize_root_mount

if TYPE_CHECKING:
    from fluxlit.app import FluxLit

DEFAULT_PIDFILE_NAME = ".fluxlit-dev.pid"
STREAMLIT_UPSTREAM_FILE_ENV = "FLUXLIT_STREAMLIT_UPSTREAM_FILE"
# Streamlit cold start can exceed the default 30s on slow disks / CI.
_STREAMLIT_TCP_WAIT_S = 60.0


def read_streamlit_upstream_url() -> str:
    """Current Streamlit base URL from :func:`write_streamlit_upstream_state` or plain env."""
    fp = (os.environ.get(STREAMLIT_UPSTREAM_FILE_ENV) or "").strip()
    if fp:
        try:
            raw = Path(fp).read_text(encoding="utf-8").strip()
        except OSError:
            raw = ""
        if raw:
            return raw.rstrip("/")
    return (os.environ.get("FLUXLIT_STREAMLIT_UPSTREAM") or "").strip().rstrip("/")


def write_streamlit_upstream_state(url: str) -> Path:
    """Write *url* to a temp file and set env for the gateway resolver and subprocesses."""
    fd, name = tempfile.mkstemp(prefix="fluxlit-upstream-", suffix=".txt", text=True)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(url.strip())
    path = Path(name)
    os.environ["FLUXLIT_STREAMLIT_UPSTREAM"] = url.strip()
    os.environ[STREAMLIT_UPSTREAM_FILE_ENV] = str(path)
    return path


def update_streamlit_upstream_file(path: Path, url: str) -> None:
    """Replace the on-disk upstream URL (e.g. after restarting Streamlit on a new port)."""
    path.write_text(url.strip(), encoding="utf-8")
    os.environ["FLUXLIT_STREAMLIT_UPSTREAM"] = url.strip()


def _start_streamlit_reload_watcher(
    on_change: Callable[[], None],
    *,
    debounce_s: float,
    stop_flag: Callable[[], bool],
) -> None:
    """Background thread: debounced filesystem watch → ``on_change`` (Streamlit restart)."""

    def run() -> None:
        try:
            from watchfiles import watch
        except ImportError:
            sys.stderr.write(
                "[fluxlit] --reload-scope=full requires the `watchfiles` package "
                "(install the same `fluxlit` environment).\n"
            )
            sys.stderr.flush()
            return
        debounce_ms = int(max(50, debounce_s * 1000))
        try:
            for _changes in watch(Path.cwd(), debounce=debounce_ms):
                if stop_flag():
                    return
                try:
                    on_change()
                except Exception as e:
                    sys.stderr.write(f"[fluxlit] Streamlit sidecar reload failed: {e}\n")
                    sys.stderr.flush()
        except Exception as e:
            sys.stderr.write(f"[fluxlit] Streamlit file watch exited: {e}\n")
            sys.stderr.flush()

    threading.Thread(target=run, daemon=True).start()


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
    path = api_mount_path if api_mount_path.startswith("/") else f"/{api_mount_path}"
    path = path.rstrip("/") or "/"
    netloc = f"{_loopback_http_host_for_client(bind_host)}:{port}"
    return urllib.parse.urlunparse(("http", netloc, path, "", "", ""))


def _fluxlit_import_hint(target: str, mod_name: str) -> str:
    return (
        f"Cannot import module {mod_name!r} for FluxLit target {target!r}. "
        "Put the package on PYTHONPATH (for example `export PYTHONPATH=$(pwd)` before "
        "`fluxlit dev`). Avoid naming your entry file `app.py` if it would shadow "
        "FluxLit's internal `fluxlit.app` package."
    )


def load_fluxlit(target: str) -> FluxLit:
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
        module = importlib.import_module(mod_name)
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


def _wait_for_tcp(host: str, port: int, timeout_s: float = 30.0) -> None:
    """Block until ``host:port`` accepts a TCP connection or ``timeout_s`` elapses."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.05)
    msg = f"Timed out waiting for {host}:{port}"
    raise TimeoutError(msg)


def _build_streamlit_env(*, target: str, api_prefix: str, internal_api_base: str) -> dict[str, str]:
    """Clone ``os.environ`` and set ``FLUXLIT_*`` variables for the Streamlit subprocess."""
    env = os.environ.copy()
    env["FLUXLIT_APP"] = target
    env["FLUXLIT_API_PREFIX"] = api_prefix
    env["FLUXLIT_INTERNAL_API_BASE"] = internal_api_base
    return env


def _build_streamlit_cmd(*, runner: Path, port: int, base_url_path: str = "") -> list[str]:
    """Command line: ``python -m streamlit run <runner>`` with headless bind on ``port``.

    Streamlit binds only to loopback on an ephemeral port; the browser talks to the
    FluxLit gateway. Disabling XSRF on this hop avoids Streamlit forcing CORS on when
    XSRF is enabled (noisy warnings and brittle proxy handshakes). CORS stays off
    because cross-origin browser traffic should not hit the sidecar directly.
    """
    cmd: list[str] = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(runner),
        "--server.headless",
        "true",
        "--server.port",
        str(port),
        "--server.address",
        "127.0.0.1",
        "--server.enableXsrfProtection",
        "false",
        "--server.enableCORS",
        "false",
        "--browser.gatherUsageStats",
        "false",
    ]
    m = normalize_root_mount(base_url_path)
    if m:
        cmd.extend(["--server.baseUrlPath", m])
    return cmd


def default_pidfile_path(explicit: Path | None = None) -> Path:
    """Path for ``fluxlit dev|run`` PID file (current directory unless overridden)."""
    if explicit is not None:
        return Path(explicit).expanduser()
    env = os.environ.get("FLUXLIT_PIDFILE", "").strip()
    if env:
        return Path(env).expanduser()
    return Path.cwd() / DEFAULT_PIDFILE_NAME


def _write_pidfile(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{os.getpid()}\n", encoding="ascii")


def _remove_pidfile(path: Path) -> None:
    with contextlib.suppress(FileNotFoundError):
        path.unlink()


def _pid_is_zombie_unix(pid: int) -> bool:
    """True if *pid* is a zombie (defunct) — :func:`os.kill` with 0 still succeeds."""
    try:
        out = subprocess.run(
            ["ps", "-p", str(pid), "-o", "stat="],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    if out.returncode != 0:
        return False
    stat = (out.stdout or "").strip()
    return bool(stat) and stat[0] == "Z"


def _pid_running(pid: int) -> bool:
    if sys.platform.startswith("win"):
        # Avoid parsing ``tasklist`` output (locale-dependent). OpenProcess is authoritative.
        import ctypes

        kernel32 = ctypes.windll.kernel32
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        ERROR_ACCESS_DENIED = 5
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if handle:
            kernel32.CloseHandle(handle)
            return True
        # ``GetLastError`` is often typed as ``Any`` in stubs; coerce for ``no-any-return``.
        return int(kernel32.GetLastError()) == ERROR_ACCESS_DENIED

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    if _pid_is_zombie_unix(pid):
        return False
    return True


def _windows_taskkill_tree(pid: int, *, force: bool) -> subprocess.CompletedProcess[str]:
    cmd = ["taskkill", "/PID", str(pid), "/T"]
    if force:
        cmd.append("/F")
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )


def shutdown_unified_process(
    pidfile: Path | None = None,
    *,
    force: bool = False,
    wait_s: float = 5.0,
) -> tuple[int, str]:
    """Stop a stack started by :func:`run_unified` using its PID file.

    Sends ``SIGTERM`` to the recorded PID (the process running Uvicorn + supervision).
    On Windows, uses ``taskkill /T`` (and ``/F`` when *force* is True) instead of
    ``os.kill``, which does not reliably terminate arbitrary processes.

    If ``force`` is True on POSIX, sends ``SIGKILL`` after *wait_s* if still running.

    Returns:
        ``(exit_code, message)`` where ``exit_code`` is 0 on success, 1 on failure
        (still running after timeout / permission error), 2 if the pidfile is missing.
    """
    path = default_pidfile_path(pidfile)
    if not path.is_file():
        return 2, f"No pid file at {path}"

    try:
        raw = path.read_text(encoding="ascii").strip()
        pid = int(raw)
    except (OSError, ValueError):
        path.unlink(missing_ok=True)
        return 0, f"Removed invalid pid file at {path}"

    if not _pid_running(pid):
        path.unlink(missing_ok=True)
        return 0, f"Removed stale pid file (pid {pid} not running)"

    if sys.platform.startswith("win"):
        # Try graceful termination first, but many headless console processes (like tests)
        # don't respond unless we force-kill; we'll escalate if still running after waiting.
        tk = _windows_taskkill_tree(pid, force=False)
        combined = f"{tk.stdout or ''}{tk.stderr or ''}"
        if tk.returncode != 0:
            lowered = combined.lower()
            if "could not find" in lowered or "not found" in lowered or "not running" in lowered:
                path.unlink(missing_ok=True)
                return 0, f"Process {pid} exited before signal was delivered"
    else:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            path.unlink(missing_ok=True)
            return 0, f"Process {pid} exited before signal was delivered"
        except PermissionError as e:
            return 1, f"Cannot signal pid {pid}: {e}"

    deadline = time.monotonic() + wait_s
    while time.monotonic() < deadline:
        if not _pid_running(pid):
            path.unlink(missing_ok=True)
            return 0, f"Stopped process {pid}"
        time.sleep(0.05)

    if sys.platform.startswith("win") and not force:
        # Escalate on Windows even without --force; otherwise headless processes often
        # survive the graceful taskkill signal indefinitely.
        _windows_taskkill_tree(pid, force=True)
        t_escalate = time.monotonic() + 2.0
        while time.monotonic() < t_escalate:
            if not _pid_running(pid):
                path.unlink(missing_ok=True)
                return 0, f"Stopped process {pid}"
            time.sleep(0.05)

    if force:
        if sys.platform.startswith("win"):
            _windows_taskkill_tree(pid, force=True)
        else:
            with contextlib.suppress(ProcessLookupError):
                os.kill(pid, signal.SIGKILL)
        t2 = time.monotonic() + 2.0
        while time.monotonic() < t2:
            if not _pid_running(pid):
                path.unlink(missing_ok=True)
                return 0, f"Killed process {pid}"
            time.sleep(0.05)

    if not _pid_running(pid):
        path.unlink(missing_ok=True)
        return 0, f"Stopped process {pid}"

    return 1, f"Process {pid} still running after {wait_s:.1f}s (try --force)"


def _terminate_process(proc: subprocess.Popen[Any], *, timeout_s: float = 5.0) -> None:
    """Try graceful interrupt, then terminate, then kill."""
    if proc.poll() is not None:
        return

    # Prefer CTRL_BREAK_EVENT on Windows; SIGINT on Unix.
    if sys.platform.startswith("win"):
        with contextlib.suppress(Exception):
            proc.send_signal(getattr(signal, "CTRL_BREAK_EVENT"))  # noqa: B009
    else:
        with contextlib.suppress(Exception):
            proc.send_signal(signal.SIGINT)

    try:
        proc.wait(timeout=timeout_s)
        return
    except subprocess.TimeoutExpired:
        pass

    with contextlib.suppress(Exception):
        proc.terminate()
    try:
        proc.wait(timeout=timeout_s)
        return
    except subprocess.TimeoutExpired:
        pass

    with contextlib.suppress(Exception):
        proc.kill()


def _inject_public_root_path(app: ASGIApp, public_mount: str) -> ASGIApp:
    """Apply ASGI ``root_path`` without Uvicorn path doubling.

    Uvicorn implements ``Config.root_path`` by prepending it to every request path.
    Reverse proxies that forward the **full** public path (e.g. ``/myapp/api/...``)
    would otherwise yield ``/myapp/myapp/api/...`` in ``scope["path"]``.

    We run Uvicorn with ``root_path=""`` and set the browser-visible mount here when
    the server left ``root_path`` empty, so both **strip-prefix** and **full-path**
    upstream shapes keep correct routing and FastAPI OpenAPI URL generation.
    """
    mount = normalize_root_mount(public_mount)
    if not mount:
        return app

    async def wrapped(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket"):
            prior = (scope.get("root_path") or "").strip()
            if not prior:
                scope = dict(scope)
                scope["root_path"] = mount
        await app(scope, receive, send)

    return wrapped


def create_gateway_app() -> ASGIApp:
    """ASGI factory for Uvicorn ``--factory`` reload mode.

    Reads ``FLUXLIT_APP`` (import target), Streamlit upstream from
    ``FLUXLIT_STREAMLIT_UPSTREAM_FILE`` or ``FLUXLIT_STREAMLIT_UPSTREAM``, and
    ``FLUXLIT_API_PREFIX`` from the environment, then returns
    :func:`fluxlit.gateway.build_gateway` over the loaded FastAPI app.

    Returns:
        An ASGI3 callable (same contract as :func:`~fluxlit.gateway.build_gateway`).

    Raises:
        RuntimeError: If ``FLUXLIT_APP`` is unset or the upstream URL cannot be resolved.
    """
    if not (os.environ.get("FLUXLIT_APP") or "").strip():
        msg = (
            "Missing required environment variable FLUXLIT_APP. "
            "Set it before using `create_gateway_app` with Uvicorn --factory "
            "(normally set by `fluxlit dev` / `fluxlit run`)."
        )
        raise RuntimeError(msg)
    if not read_streamlit_upstream_url():
        msg = (
            "Missing Streamlit upstream URL. Set FLUXLIT_STREAMLIT_UPSTREAM and/or "
            "FLUXLIT_STREAMLIT_UPSTREAM_FILE (normally set by `fluxlit dev` / `fluxlit run`)."
        )
        raise RuntimeError(msg)
    target = os.environ["FLUXLIT_APP"].strip()
    api_prefix = os.environ.get("FLUXLIT_API_PREFIX", "/api")
    fl = load_fluxlit(target)
    mount = normalize_root_mount(fl.settings.public_mount_path())
    return _inject_public_root_path(
        build_gateway(
            fl.api,
            "",
            upstream_resolver=read_streamlit_upstream_url,
            access_log=fl.settings.enable_gateway_access_log,
            api_prefix=api_prefix,
            root_mount=mount,
        ),
        mount,
    )


def run_unified(
    target: str,
    *,
    host: str = "127.0.0.1",
    port: int = 8000,
    reload: bool = False,
    reload_scope: str = "gateway",
    log_level: str = "info",
    proxy_headers: bool = False,
    forwarded_allow_ips: str | None = None,
    pidfile: Path | None = None,
    write_pidfile: bool = True,
) -> None:
    """Start Streamlit on a free localhost port and Uvicorn on ``host:port``.

    Sets process environment so ``create_gateway_app`` / Streamlit entry can resolve
    the app and internal API base (loopback-safe URL derived from ``host``, ``port``,
    and ``api_mount_path``). If Streamlit
    exits, the gateway is stopped. On shutdown, the Streamlit child receives SIGINT /
    terminate / kill (platform-dependent).

    Args:
        target: ``module:fluxlit_instance`` import path.
        host: Uvicorn bind host.
        port: Uvicorn bind port (public).
        reload: If True, use Uvicorn reload with :func:`create_gateway_app`.
        reload_scope: ``gateway`` (default) or ``full``. ``full`` also restarts Streamlit
            when watched files change (requires ``watchfiles``); see CLI ``--reload-scope``.
        log_level: Uvicorn log level.
        proxy_headers: Forwarded to :class:`uvicorn.Config`.
        forwarded_allow_ips: Forwarded to :class:`uvicorn.Config`.
        pidfile: Optional explicit path for the PID file (see :func:`default_pidfile_path`).
        write_pidfile: If False, do not create a PID file (also skipped when
            ``FLUXLIT_NO_PIDFILE`` is ``1`` / ``true`` / ``yes``).
    """
    streamlit_port = find_free_port()
    runner = Path(__file__).resolve().parent / "streamlit_main.py"

    fl = load_fluxlit(target)

    scope = (reload_scope or "gateway").strip().lower()
    if reload and scope not in {"gateway", "full"}:
        msg = "reload_scope must be 'gateway' or 'full'"
        raise ValueError(msg)

    api_prefix = fl.settings.api_mount_path
    internal_api_base = internal_api_base_url(bind_host=host, port=port, api_mount_path=api_prefix)
    mount = normalize_root_mount(fl.settings.public_mount_path())
    use_proxy = proxy_headers or fl.settings.trust_proxy
    allow_ips = forwarded_allow_ips
    if use_proxy and allow_ips is None:
        allow_ips = fl.settings.forwarded_allow_ips or "*"

    env = _build_streamlit_env(
        target=target,
        api_prefix=api_prefix,
        internal_api_base=internal_api_base,
    )
    cmd = _build_streamlit_cmd(
        runner=runner, port=streamlit_port, base_url_path=fl.settings.public_mount_path()
    )

    popen_kwargs: dict[str, Any] = {"env": env}
    if sys.platform.startswith("win"):
        # New process group so we can send CTRL_BREAK_EVENT.
        popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP")  # noqa: B009
    else:
        popen_kwargs["start_new_session"] = True

    proc_box: list[subprocess.Popen[Any]] = [subprocess.Popen(cmd, **popen_kwargs)]
    streamlit_restart_lock = threading.Lock()
    streamlit_reload_state: dict[str, bool] = {"intentional": False}
    streamlit_reload_done = threading.Event()
    pidfile_path: Path | None = None
    pidfile_written = False
    upstream_state_path: Path | None = None
    no_pf = os.environ.get("FLUXLIT_NO_PIDFILE", "").strip().lower() in {"1", "true", "yes"}
    try:
        _wait_for_tcp("127.0.0.1", streamlit_port, timeout_s=_STREAMLIT_TCP_WAIT_S)
        upstream = f"http://127.0.0.1:{streamlit_port}"
        os.environ["FLUXLIT_APP"] = target
        os.environ["FLUXLIT_API_PREFIX"] = api_prefix
        upstream_state_path = write_streamlit_upstream_state(upstream)

        if write_pidfile and not no_pf:
            pidfile_path = default_pidfile_path(pidfile)
            _write_pidfile(pidfile_path)
            pidfile_written = True

        if reload:
            if scope == "full":
                sys.stderr.write(
                    "[fluxlit] --reload --reload-scope=full: Uvicorn reload plus Streamlit "
                    "restart on file changes (best-effort; WebSockets reconnect).\n"
                )
            else:
                sys.stderr.write(
                    "[fluxlit] --reload --reload-scope=gateway: only the API gateway reloads; "
                    "Streamlit does not. Use --reload-scope=full to restart Streamlit too.\n"
                )
            sys.stderr.flush()
            config = uvicorn.Config(
                "fluxlit.runtime:create_gateway_app",
                host=host,
                port=port,
                factory=True,
                reload=True,
                log_level=log_level,
                root_path="",
                proxy_headers=use_proxy,
                forwarded_allow_ips=allow_ips,
            )
        else:
            config = uvicorn.Config(
                _inject_public_root_path(
                    build_gateway(
                        fl.api,
                        "",
                        upstream_resolver=read_streamlit_upstream_url,
                        access_log=fl.settings.enable_gateway_access_log,
                        api_prefix=fl.settings.api_mount_path,
                        root_mount=mount,
                    ),
                    mount,
                ),
                host=host,
                port=port,
                log_level=log_level,
                root_path="",
                proxy_headers=use_proxy,
                forwarded_allow_ips=allow_ips,
            )

        server = uvicorn.Server(config)

        def monitor_streamlit() -> None:
            while not server.should_exit:
                p = proc_box[0]
                code = p.wait()
                with streamlit_restart_lock:
                    reloading = streamlit_reload_state["intentional"]
                if reloading:
                    if streamlit_reload_done.wait(timeout=_STREAMLIT_TCP_WAIT_S):
                        streamlit_reload_done.clear()
                    with streamlit_restart_lock:
                        streamlit_reload_state["intentional"] = False
                    continue
                if not server.should_exit:
                    sys.stderr.write(
                        f"[fluxlit] Streamlit exited (code={code}); stopping gateway.\n"
                    )
                    sys.stderr.flush()
                    server.should_exit = True
                return

        threading.Thread(target=monitor_streamlit, daemon=True).start()

        if reload and scope == "full" and upstream_state_path is not None:
            path_for_updates = upstream_state_path

            def restart_streamlit_sidecar() -> None:
                try:
                    with streamlit_restart_lock:
                        streamlit_reload_state["intentional"] = True
                        streamlit_reload_done.clear()
                    _terminate_process(proc_box[0])
                    new_port = find_free_port()
                    cmd_local = _build_streamlit_cmd(
                        runner=runner,
                        port=new_port,
                        base_url_path=fl.settings.public_mount_path(),
                    )
                    new_proc = subprocess.Popen(cmd_local, **popen_kwargs)
                    proc_box[0] = new_proc
                    try:
                        _wait_for_tcp("127.0.0.1", new_port, timeout_s=_STREAMLIT_TCP_WAIT_S)
                    except TimeoutError:
                        _terminate_process(new_proc)
                        sys.stderr.write(
                            "[fluxlit] Streamlit sidecar reload failed: timed out waiting for the "
                            "new process to listen; restart `fluxlit dev` (or `fluxlit run`).\n"
                        )
                        sys.stderr.flush()
                        if not server.should_exit:
                            server.should_exit = True
                        return
                    new_upstream = f"http://127.0.0.1:{new_port}"
                    update_streamlit_upstream_file(path_for_updates, new_upstream)
                finally:
                    with streamlit_restart_lock:
                        streamlit_reload_done.set()

            _start_streamlit_reload_watcher(
                restart_streamlit_sidecar,
                debounce_s=0.25,
                stop_flag=lambda: server.should_exit,
            )

        server.run()
    finally:
        if upstream_state_path is not None:
            with contextlib.suppress(OSError):
                upstream_state_path.unlink(missing_ok=True)
        if STREAMLIT_UPSTREAM_FILE_ENV in os.environ:
            del os.environ[STREAMLIT_UPSTREAM_FILE_ENV]
        if pidfile_written and pidfile_path is not None:
            _remove_pidfile(pidfile_path)
        _terminate_process(proc_box[0])
