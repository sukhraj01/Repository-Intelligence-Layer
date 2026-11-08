"""Screen prompts before they leave the machine. Implements ``docs/RQ3_PILOT.md`` ("Terms of use").

The unpaid provider quota allows submitted text to be used for the provider's products and read by
reviewers, so the pilot sends public repository text only. ``screen_text`` rejects a prompt that
holds a path under a home directory, a string shaped like a credential, or an e-mail address that
is not on the reviewed list. Public source files and issues do carry addresses (project contacts,
author lines, placeholders), so the list holds the SHA-256 of each reviewed lowercase address and
no address is written to a tracked file. ``forbidden`` addresses (the operator's own identity) are
rejected even if listed.

The prompts of the RQ3 runs are pseudonymised first (``pseudonymise.py``, D120): the screen accepts
exactly ``person<N>@example.invalid`` and ``user<N>`` in the user-name position of a home path, and
nothing else beyond what it accepted before.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from ril.agent.providers.pseudonymise import EMAIL, PLACEHOLDER_EMAIL, PLACEHOLDER_PATH

HOME_PATH = re.compile(
    r"(?:/Users/[A-Za-z0-9._-]+|/home[0-9]*/[A-Za-z0-9._-]+|[A-Za-z]:\\Users\\[^\\\s]+)"
)
TOKEN = re.compile(
    r"AIza[0-9A-Za-z_-]{35}|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{20,}"
    r"|sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{10,}"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----"
)


@dataclass(frozen=True)
class Finding:
    kind: str  # "home_path", "email" or "token"
    digest: str  # sha256 of the matched text, so a finding can be reviewed without printing it


def email_digest(address: str) -> str:
    return hashlib.sha256(address.strip().lower().encode("utf-8")).hexdigest()


def load_allowed_digests(path: str | Path) -> frozenset[str]:
    """Digests from a file with one per line; ``#`` starts a comment."""
    out: set[str] = set()
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        field = line.split("#", 1)[0].strip()
        if field:
            out.add(field)
    return frozenset(out)


def screen_text(
    text: str,
    allowed_email_digests: Collection[str] = (),
    forbidden_emails: Iterable[str] = (),
) -> list[Finding]:
    """Findings in ``text``; empty means it may be sent."""
    forbidden = {email_digest(a) for a in forbidden_emails if a}
    found = [
        Finding("home_path", hashlib.sha256(m.group(0).encode()).hexdigest())
        for m in HOME_PATH.finditer(text)
        if not PLACEHOLDER_PATH.match(text, m.start())
    ]
    found += [
        Finding("token", hashlib.sha256(m.group(0).encode()).hexdigest())
        for m in TOKEN.finditer(text)
    ]
    for m in EMAIL.finditer(text):
        if PLACEHOLDER_EMAIL.fullmatch(m.group(0)):
            continue  # the pseudonymised form (``pseudonymise.py``), the only new form accepted
        d = email_digest(m.group(0))
        if d in forbidden or d not in allowed_email_digests:
            found.append(Finding("email", d))
    return found


def screen_items(
    items: Iterable[Mapping[str, str]],
    allowed_email_digests: Collection[str] = (),
    forbidden_emails: Iterable[str] = (),
) -> dict[str, list[Finding]]:
    """Findings per ``"<instance>/<arm>"`` for prepared items (each with a ``prompt``)."""
    forbidden = tuple(forbidden_emails)
    out: dict[str, list[Finding]] = {}
    for it in items:
        f = screen_text(str(it["prompt"]), allowed_email_digests, forbidden)
        if f:
            out[f"{it['instance_id']}/{it['arm']}"] = f
    return out
