from __future__ import annotations

import os
import platform
import socket
from datetime import UTC, datetime
from functools import lru_cache

from app.config import get_settings

STARTED_AT = datetime.now(UTC)


@lru_cache
def hostname() -> str:
    return socket.gethostname()


def instance_id() -> str:
    settings = get_settings()
    return settings.instance_id or hostname()


def instance_info() -> dict[str, str | int | float]:
    now = datetime.now(UTC)
    uptime = (now - STARTED_AT).total_seconds()
    return {
        "instance_id": instance_id(),
        "hostname": hostname(),
        "pid": os.getpid(),
        "platform": platform.platform(),
        "started_at": STARTED_AT.isoformat(),
        "uptime_seconds": int(uptime),
        "tls_terminated_here": False,
    }
