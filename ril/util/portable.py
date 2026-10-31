"""Neutral spelling of home-directory paths for anything written to a tracked record.

Run records carry absolute paths (result and checkpoint directories). Those are useful on the
machine that made them but expose the login name and mean nothing elsewhere, so the stored copy
uses ``/home/<user>/...``. The live record handed to callers keeps the real paths.
"""

from __future__ import annotations

import re
from typing import Any

NEUTRAL_HOME = "/home/<user>"
# One group per platform spelling; shared with the review scan so both agree on what a home path is.
HOME_PATH_RE = re.compile(
    r"(?<![\w.])(?:/Users/(?P<mac>[A-Za-z0-9._-]+)|/home\d*/(?P<lin>[A-Za-z0-9._-]+)"
    r"|[A-Za-z]:\\Users\\(?P<win>[A-Za-z0-9._-]+))"
)


def neutral_paths(value: Any) -> Any:
    """Return ``value`` with every home-directory prefix in its strings replaced by the token.

    Walks dicts, lists and tuples; other types pass through. The input is not modified.
    """
    if isinstance(value, str):
        return HOME_PATH_RE.sub(NEUTRAL_HOME, value)
    if isinstance(value, dict):
        return {k: neutral_paths(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [neutral_paths(v) for v in value]
    return value
