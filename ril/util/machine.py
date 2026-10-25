"""Machine description recorded with every run (host, platform, Python, CPUs, memory).

Kept compatible with Python 3.10.
"""

from __future__ import annotations

import os
import platform
from typing import Any


def hardware() -> dict[str, Any]:
    """Machine description recorded with every run."""
    info: dict[str, Any] = {
        "host": platform.node(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "cpus_visible": os.cpu_count(),
    }
    try:
        with open("/proc/meminfo", encoding="ascii") as handle:
            info["mem_total_kb"] = int(handle.readline().split()[1])
    except (OSError, ValueError, IndexError):
        info["mem_total_kb"] = None
    return info
