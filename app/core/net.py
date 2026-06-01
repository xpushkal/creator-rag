"""Global IPv4 preference.

On networks with broken/unrouted IPv6, Python's default connect tries an
IPv6 address first and blocks for the full ~75s TCP connect timeout before
falling back to IPv4 (curl avoids this via Happy Eyeballs). That penalty hit
every outbound call — the LLM SDK, yt-dlp, and youtube-transcript-api — and was
the real cause of "ingestion is slow".

Filtering getaddrinfo to IPv4 results fixes it for every library at once
(requests, urllib, httpx, ...) in one place. Idempotent.
"""
from __future__ import annotations

import socket

_patched = False


def force_ipv4() -> None:
    global _patched
    if _patched:
        return
    _orig = socket.getaddrinfo

    def ipv4_only(host, *args, **kwargs):
        results = _orig(host, *args, **kwargs)
        ipv4 = [r for r in results if r[0] == socket.AF_INET]
        # Fall back to whatever resolved if a host is genuinely IPv6-only.
        return ipv4 or results

    socket.getaddrinfo = ipv4_only
    _patched = True
