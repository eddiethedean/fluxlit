"""PID file helpers, process liveness checks, and graceful shutdown of ``run_unified`` stacks."""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from fluxlit.runtime.constants import DEFAULT_PIDFILE_NAME


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
        # Avoid parsing ``tasklist`` output (locale-dependent). OpenProcess alone is not
        # enough: a terminated child can still be opened until the parent reaps it, so we
        # must consult ``GetExitCodeProcess`` (``STILL_ACTIVE`` means still running).
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        ERROR_ACCESS_DENIED = 5
        STILL_ACTIVE = 259
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if handle:
            exit_code = wintypes.DWORD()
            ok = int(kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)))
            kernel32.CloseHandle(handle)
            if ok:
                return int(exit_code.value) == STILL_ACTIVE
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
    """Stop a stack started by :func:`fluxlit.runtime.run_unified` using its PID file.

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
        # Prefer `os.kill(..., SIGTERM)` first: it reliably terminates Python processes
        # (including the ones spawned in our tests). Fall back to taskkill for non-Python
        # or permission edge cases.
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            path.unlink(missing_ok=True)
            return 0, f"Process {pid} exited before signal was delivered"
        except Exception:
            tk = _windows_taskkill_tree(pid, force=False)
            combined = f"{tk.stdout or ''}{tk.stderr or ''}"
            if tk.returncode != 0:
                lowered = combined.lower()
                if (
                    "could not find" in lowered
                    or "not found" in lowered
                    or "not running" in lowered
                ):
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
        # If SIGTERM didn't work, escalate with taskkill /F (same behavior as --force on
        # POSIX where we follow SIGTERM with SIGKILL).
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
