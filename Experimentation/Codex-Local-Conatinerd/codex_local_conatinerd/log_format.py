import re

from datetime import datetime


_ANSI_ESCAPE_RE = re.compile(
    r"""
    \x1B  # ESC
    (?:
        \[ [0-?]* [ -/]* [@-~]   # CSI ... cmd
      | \] .*? (?:\x07|\x1B\\)   # OSC ... BEL or ST
      | .                       # single-char escape
    )
    """,
    re.VERBOSE,
)

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")

_DOCKER_LOG_PREFIX_RE = re.compile(
    r"^(?P<ts>\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)?)\s+(?P<msg>.*)$"
)


def parse_docker_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None

    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    tz_index = max(text.rfind("+"), text.rfind("-"))
    if tz_index > 10:
        main, tz = text[:tz_index], text[tz_index:]
    else:
        main, tz = text, ""

    if "." in main:
        prefix, frac = main.split(".", 1)
        frac_digits = "".join(ch for ch in frac if ch.isdigit())
        frac_digits = (frac_digits[:6]).ljust(6, "0") if frac_digits else "000000"
        main = f"{prefix}.{frac_digits}"

    try:
        return datetime.fromisoformat(main + tz)
    except ValueError:
        return None


def prettify_log_line(line: str) -> str:
    text = (line or "").replace("\r", "")
    text = _ANSI_ESCAPE_RE.sub("", text)
    text = _CONTROL_CHARS_RE.sub("", text)

    match = _DOCKER_LOG_PREFIX_RE.match(text)
    if match:
        ts = match.group("ts")
        msg = match.group("msg")
        dt = parse_docker_datetime(ts)
        if dt is not None:
            time_part = dt.astimezone().strftime("%H:%M:%S")
        else:
            time_part = ts[11:19] if len(ts) >= 19 else ts
        text = f"[{time_part}] {msg}"

    text = re.sub(r"[ \t]{2,}", " ", text).strip()
    return text

