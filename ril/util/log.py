"""Project logger. All output goes through here; the package never calls ``print``."""

from __future__ import annotations

import logging

_ROOT = "ril"
_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a logger under the ``ril`` namespace, configuring the root handler once."""
    root = logging.getLogger(_ROOT)
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(_FORMAT))
        root.addHandler(handler)
        root.setLevel(logging.INFO)
        root.propagate = False
    return root if not name else logging.getLogger(f"{_ROOT}.{name}")
