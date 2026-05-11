"""CLI-style entry: spawn Streamlit sidecar, optional reload watcher, run Uvicorn."""

from __future__ import annotations

import contextlib
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

import uvicorn

from fluxlit.gateway import build_gateway, normalize_root_mount
from fluxlit.runtime.constants import _STREAMLIT_TCP_WAIT_S
from fluxlit.runtime.import_target import find_free_port, internal_api_base_url, load_fluxlit
from fluxlit.runtime.process_control import _remove_pidfile, _write_pidfile, default_pidfile_path
from fluxlit.runtime.public_mount import _inject_public_root_path
from fluxlit.runtime.reload_watcher import _start_streamlit_reload_watcher
from fluxlit.runtime.streamlit_proc import (
    _build_streamlit_cmd,
    _build_streamlit_env,
    _StreamlitPopenKwargs,
    _terminate_process,
)
from fluxlit.runtime.upstream_state import (
    STREAMLIT_UPSTREAM_FILE_ENV,
    read_streamlit_upstream_url,
    update_streamlit_upstream_file,
    write_streamlit_upstream_state,
)
from fluxlit.runtime.wait_tcp import _invoke_wait_for_tcp

_STREAMLIT_MAIN = Path(__file__).resolve().parent.parent / "streamlit" / "main.py"


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
    runner = _STREAMLIT_MAIN

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
        runner=runner,
        port=streamlit_port,
        base_url_path=fl.settings.public_mount_path(),
        extra_cli_args=fl.settings.streamlit_run_cli_args,
    )

    popen_kwargs: _StreamlitPopenKwargs = {"env": env}
    if sys.platform.startswith("win"):
        # New process group so we can send CTRL_BREAK_EVENT.
        popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP")  # noqa: B009
    else:
        popen_kwargs["start_new_session"] = True

    proc_box: list[subprocess.Popen[bytes]] = [subprocess.Popen(cmd, **popen_kwargs)]
    streamlit_restart_lock = threading.Lock()
    streamlit_reload_state: dict[str, bool] = {"intentional": False}
    streamlit_reload_done = threading.Event()
    pidfile_path: Path | None = None
    pidfile_written = False
    upstream_state_path: Path | None = None
    no_pf = os.environ.get("FLUXLIT_NO_PIDFILE", "").strip().lower() in {"1", "true", "yes"}
    try:
        _invoke_wait_for_tcp("127.0.0.1", streamlit_port, timeout_s=_STREAMLIT_TCP_WAIT_S)
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
            _grace = fl.settings.uvicorn_graceful_shutdown_timeout_s
            # Uvicorn's Config accepts many optional kwargs; keep a loose dict for forward compat.
            _reload_kw: dict[str, Any] = {
                "host": host,
                "port": port,
                "factory": True,
                "reload": True,
                "log_level": log_level,
                "root_path": "",
                "proxy_headers": use_proxy,
                "forwarded_allow_ips": allow_ips,
            }
            if _grace is not None:
                _reload_kw["timeout_graceful_shutdown"] = _grace
            config = uvicorn.Config("fluxlit.runtime:create_gateway_app", **_reload_kw)
        else:
            _grace = fl.settings.uvicorn_graceful_shutdown_timeout_s
            # Same as reload branch: mirror uvicorn.Config keyword surface without pinning stubs.
            _plain_kw: dict[str, Any] = {
                "host": host,
                "port": port,
                "log_level": log_level,
                "root_path": "",
                "proxy_headers": use_proxy,
                "forwarded_allow_ips": allow_ips,
            }
            if _grace is not None:
                _plain_kw["timeout_graceful_shutdown"] = _grace
            config = uvicorn.Config(
                _inject_public_root_path(
                    build_gateway(
                        fl.api,
                        "",
                        upstream_resolver=read_streamlit_upstream_url,
                        access_log=fl.settings.enable_gateway_access_log,
                        api_prefix=fl.settings.api_mount_path,
                        root_mount=mount,
                        proxy_settings=fl.settings,
                    ),
                    mount,
                ),
                **_plain_kw,
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
                        extra_cli_args=fl.settings.streamlit_run_cli_args,
                    )
                    new_proc = subprocess.Popen(cmd_local, **popen_kwargs)
                    proc_box[0] = new_proc
                    try:
                        _invoke_wait_for_tcp("127.0.0.1", new_port, timeout_s=_STREAMLIT_TCP_WAIT_S)
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
