#!/usr/bin/env python3
"""WebSocket handshake to Streamlit's `/_stcore/stream` through the gateway + proxy."""

from __future__ import annotations

import asyncio
import os
import ssl
import sys


async def _main() -> int:
    try:
        import websockets
    except ImportError:
        print("FAIL: install websockets (pip install websockets)", file=sys.stderr)
        return 1

    url = os.environ.get("WS_URL", "").strip()
    if not url:
        print("FAIL: WS_URL not set", file=sys.stderr)
        return 1

    ssl_ctx: ssl.SSLContext | None = None
    if url.startswith("wss://"):
        if os.environ.get("CURL_INSECURE", "") == "1":
            ssl_ctx = ssl.create_default_context()
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE

    try:
        async with websockets.connect(
            url,
            subprotocols=["streamlit"],
            ssl=ssl_ctx,
            open_timeout=20,
        ):
            pass
    except Exception as exc:
        print(f"FAIL: websocket connect {url!r}: {exc}", file=sys.stderr)
        return 1

    print("WebSocket handshake OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
