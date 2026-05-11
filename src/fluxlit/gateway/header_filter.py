"""ASGI request header filtering for upstream proxy hops."""

from __future__ import annotations


def filter_request_headers(raw: list[tuple[bytes, bytes]]) -> list[tuple[bytes, bytes]]:
    hop_by_hop = {
        b"connection",
        b"keep-alive",
        b"proxy-authenticate",
        b"proxy-authorization",
        b"te",
        b"trailers",
        b"transfer-encoding",
        b"upgrade",
    }
    # Drop client-supplied forwarding headers; the gateway sets authoritative values.
    strip = hop_by_hop | {
        b"x-forwarded-for",
        b"x-forwarded-host",
        b"x-forwarded-proto",
        b"x-forwarded-port",
        b"x-forwarded-prefix",
    }
    out: list[tuple[bytes, bytes]] = []
    for k, v in raw:
        kl = k.lower()
        if kl in strip:
            continue
        if kl == b"host":
            continue
        out.append((k, v))
    return out
