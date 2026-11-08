"""Which exceptions end a mining session and which quarantine one pull request (DEV-036).

Implements ``docs/experiments/B.md`` E-MINE-FULL, decisions 1 and 2 of the third relaunch. An
exception raised while one pull request's content is processed (checkout, parsing, mapping,
unit-id construction) says something about that pull request, so the pull request is quarantined
with the reason ``corpus_error:<ExceptionClass>`` and the session goes on. An exception that says
something about the machine, the network or the service is not a content error: it propagates, the
miner process exits non-zero, and the job script relaunches it (resuming from the state file).

The two classes are told apart by exception type alone (:func:`is_infrastructure_error`).
"""

from __future__ import annotations

import errno
import http.client
import subprocess
import urllib.error

from ril.data_mining.github_api import ApiError, TransportError

INFRASTRUCTURE_TYPES: tuple[type[BaseException], ...] = (
    ApiError,  # the service refused or failed (rate limit, 5xx after the client's retries)
    urllib.error.URLError,
    http.client.HTTPException,
    ConnectionError,
    TransportError,
    TimeoutError,
    subprocess.TimeoutExpired,
    MemoryError,
)
"""Types that always mean a fault outside the pull request (``TransportError`` is an ``OSError``
raised without an errno, so it is listed here and not left to the errno rule)."""

INFRASTRUCTURE_ERRNOS = frozenset(
    {
        errno.ENOSPC,
        errno.EDQUOT,
        errno.EIO,
        errno.ENOMEM,
        errno.EROFS,
        errno.ESTALE,
        errno.EMFILE,
        errno.ENFILE,
        errno.ENETDOWN,
        errno.ENETUNREACH,
        errno.ENETRESET,
        errno.ECONNRESET,
        errno.ECONNABORTED,
        errno.ETIMEDOUT,
        errno.EHOSTUNREACH,
        errno.EHOSTDOWN,
    }
)
"""An ``OSError`` with one of these errors is the disk, quota, memory or network of the node. Any
other ``OSError`` (a file name too long, an illegal byte sequence in a name) is about the content
of the pull request."""


def is_infrastructure_error(exc: BaseException) -> bool:
    """True for network, API, disk, quota, memory and node faults; False for content errors."""
    if isinstance(exc, INFRASTRUCTURE_TYPES):
        return True
    if isinstance(exc, OSError):
        return exc.errno in INFRASTRUCTURE_ERRNOS
    return False


def corpus_error_reason(exc: BaseException) -> str:
    """The quarantine reason of a content error."""
    return f"corpus_error:{type(exc).__name__}"
