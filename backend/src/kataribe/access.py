"""Who may reach what, once the app is on a public URL.

Two audiences share one address. A relative arrives at a link to one person's
family page and must get there with nothing to sign in to. The team's console,
with every transcript and every recording, private stories included, must not be
reachable by anyone else at all.

So everything is closed behind the team password except what a family page
needs. With no password set, as in local development, everything is open.
"""

import base64
import binascii
import re
import secrets

PUBLIC = [
    re.compile(r"/family/[\w-]+/?"),  # the family page itself
    re.compile(r"/api/family/.+"),  # what it reads, the questions it sends, the quote clips
    re.compile(r"/api/health"),
    re.compile(r"/assets/[\w.-]+"),  # the built page's scripts and styles
    re.compile(r"/[\w-]+\.(?:svg|ico|png)"),  # icons at the root
]


def is_public(path: str) -> bool:
    return any(pattern.fullmatch(path) for pattern in PUBLIC)


def is_team(authorization: str | None, password: str) -> bool:
    """HTTP Basic, any user name, the team password. The browser asks once and
    then sends it with every request the console makes."""
    scheme, _, encoded = (authorization or "").partition(" ")
    if scheme.lower() != "basic":
        return False
    try:
        _, _, given = base64.b64decode(encoded, validate=True).decode().partition(":")
    except (binascii.Error, UnicodeDecodeError):
        return False
    return secrets.compare_digest(given.encode(), password.encode())
