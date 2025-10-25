import socket


def get_local_ip(fallback: str | None = None) -> str:
    """
    Returns the primary local IP address for this machine.
    Uses a UDP socket trick which avoids external traffic.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError as exc:
        if fallback is not None:
            return fallback
        raise RuntimeError("Unable to determine a local IP address") from exc
