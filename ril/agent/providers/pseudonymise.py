"""Pseudonymise a prompt before it is sent and restore the reply. Implements ``docs/RQ3_PILOT.md``
("Terms of use", D120).

Issues and source files carry e-mail addresses (placeholders, maintainers, author lines) and the
home-directory paths of whoever pasted a traceback. The prompt screen refuses both, and refusing
them would make the sample depend on whether an issue quotes a traceback. Instead, after the
context is assembled and before the screen, ``pseudonymise`` replaces

* every e-mail address by ``person<N>@example.invalid`` (reserved domain), and
* the user-name segment of every home-directory path (``/home/<name>``, ``/Users/<name>``,
  ``C:\\Users\\<name>``) by ``user<N>``,

with N numbered by first occurrence in the prompt, separately for the two kinds, by the same rule
for every arm and instance. The mapping of one prompt is returned (and stored with the prompt by
``rq3_prompts.prepare_screened``, never printed). ``restore_text`` applies the inverse to a reply
before its edit blocks are converted, so an edit that quotes a placeholder matches the original
file and writes the original text.

Both passes are bijective on a prompt: every address and every path user name of the original is
replaced (including strings that already look like a placeholder), so ``restore_text`` of the
transformed text is the original text; ``tests/unit/test_pseudonymise.py`` and the preparation
step check it. A user name is replaced only in path position, so the same word elsewhere in the
code is left alone. Restoring is applied to the whole reply (the FILE lines too, so a repository
path that happens to contain ``/home/<name>`` still matches the context's path list).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

TRANSFORM_VERSION = "rq3-pseudonymise/v1"

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
"""Shape of an address; the prompt screen uses this same pattern."""
_PREFIX = r"(?:/Users/|/home[0-9]*/|[A-Za-z]:\\Users\\)"
# The user name as the transform reads it: ASCII letters, digits and ``._-``, ending in a letter,
# digit or underscore, so sentence punctuation after a path stays outside the name and the name is
# never longer than what the screen's own path pattern matches.
_NAME = r"[A-Za-z0-9._-]*[A-Za-z0-9_]"
_TAIL = r"(?![A-Za-z0-9._-]*[A-Za-z0-9_])"
PATH_NAME = re.compile(rf"(?P<pre>{_PREFIX})(?P<name>{_NAME})")
PLACEHOLDER_PATH = re.compile(rf"(?P<pre>{_PREFIX})user(?P<n>[0-9]+){_TAIL}")
PLACEHOLDER_EMAIL = re.compile(
    r"(?<![A-Za-z0-9._%+-])person(?P<n>[0-9]+)@example\.invalid(?![A-Za-z0-9-])(?!\.[A-Za-z0-9-])"
)


@dataclass(frozen=True)
class PseudonymMap:
    """Placeholder to original, per kind, for one prompt."""

    emails: Mapping[str, str] = field(default_factory=dict)
    users: Mapping[str, str] = field(default_factory=dict)

    @property
    def touched(self) -> str:
        """``none``, ``email``, ``path`` or ``both``."""
        e, u = bool(self.emails), bool(self.users)
        return "both" if e and u else "email" if e else "path" if u else "none"

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": TRANSFORM_VERSION,
            "emails": dict(self.emails),
            "users": dict(self.users),
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> PseudonymMap:
        if d.get("version") != TRANSFORM_VERSION:
            raise ValueError(f"unknown pseudonym map version {d.get('version')!r}")
        return cls(dict(d["emails"]), dict(d["users"]))


def pseudonymise(text: str) -> tuple[str, PseudonymMap]:
    """``(text with placeholders, mapping)``; the same text always gives the same result."""
    emails: dict[str, str] = {}  # original -> placeholder, in order of first occurrence

    def mail(m: re.Match[str]) -> str:
        return emails.setdefault(m.group(0), f"person{len(emails) + 1}@example.invalid")

    step = EMAIL.sub(mail, text)
    users: dict[str, str] = {}

    def path(m: re.Match[str]) -> str:
        name = users.setdefault(m.group("name"), f"user{len(users) + 1}")
        return m.group("pre") + name

    out = PATH_NAME.sub(path, step)
    return out, PseudonymMap({v: k for k, v in emails.items()}, {v: k for k, v in users.items()})


def restore_text(text: str, mapping: PseudonymMap | None) -> str:
    """Inverse of ``pseudonymise`` for a text that quotes the prompt's placeholders.

    Undoes the two passes in the opposite order. A placeholder the prompt did not contain is left
    as it is (a model cannot have been shown it).
    """
    if mapping is None or not (mapping.emails or mapping.users):
        return text

    def path(m: re.Match[str]) -> str:
        name = mapping.users.get(f"user{m.group('n')}")
        return m.group(0) if name is None else m.group("pre") + name

    def mail(m: re.Match[str]) -> str:
        return mapping.emails.get(m.group(0), m.group(0))

    return PLACEHOLDER_EMAIL.sub(mail, PLACEHOLDER_PATH.sub(path, text))


def quote_text(text: str, mapping: PseudonymMap) -> str:
    """How a model shown the pseudonymised prompt would quote ``text`` of the original: the
    prompt's own addresses and path user names replaced by their placeholders (others unchanged).

    Used by the round-trip checks, never on the send path.
    """
    mail_of = {v: k for k, v in mapping.emails.items()}
    user_of = {v: k for k, v in mapping.users.items()}

    def path(m: re.Match[str]) -> str:
        return m.group("pre") + user_of.get(m.group("name"), m.group("name"))

    def mail(m: re.Match[str]) -> str:
        return mail_of.get(m.group(0), m.group(0))

    return PATH_NAME.sub(path, EMAIL.sub(mail, text))
