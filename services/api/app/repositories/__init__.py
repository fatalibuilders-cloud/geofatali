"""Repositories: the only code that touches the database.

Two rules hold across every function here.

**Ownership is enforced on read, not on write.** Every lookup is scoped by the
requesting user, and a row belonging to someone else is reported as *not
found* rather than *forbidden*. A 403 would confirm that the id exists, which
tells an attacker enumerating ids exactly what they wanted to know.

**Nested resources resolve through their project.** There is no way to fetch a
borehole by id alone. It is always "this borehole, in this project, which this
user may see", so an authorisation check cannot be forgotten at one call site.
"""

from __future__ import annotations


class NotFound(LookupError):
    """The row does not exist, or the requester may not see it. Deliberately the same."""


class Conflict(ValueError):
    """The write contradicts something already stored."""


class Immutable(ValueError):
    """An attempt to change a record that is evidence rather than state."""
