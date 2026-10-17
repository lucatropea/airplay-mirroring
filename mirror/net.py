from __future__ import annotations

import socket


def lan_ip() -> str:
    """Local IPv4 used for outbound traffic (reachable from the iPad on Wi‑Fi)."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))
        return str(probe.getsockname()[0])
    except OSError:
        return "127.0.0.1"
    finally:
        probe.close()
