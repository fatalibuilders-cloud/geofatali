"""Schema management from the command line.

    python -m app.db.cli migrate     apply everything not yet applied
    python -m app.db.cli version     print the current schema version
    python -m app.db.cli check       exit non-zero if migrations are pending

Until this existed the migrations were only ever applied by the test suite,
which meant a real deployment came up with no tables and failed every request
with "relation does not exist". The container entrypoint runs `migrate` before
starting the server.
"""

from __future__ import annotations

import sys

from .base import engine
from .migrate import MigrationError, applied, current_version, discover, migrate


def _migrate() -> int:
    run = migrate(engine())
    if run:
        print(f"Applied {len(run)} migration(s): {', '.join(run)}")
    else:
        print(f"Schema is up to date at {current_version(engine())}.")
    return 0


def _version() -> int:
    version = current_version(engine())
    print(version or "no migrations applied")
    return 0


def _check() -> int:
    done = set(applied(engine()))
    pending = [f"{v}_{n}" for v, n, _ in discover() if v not in done]
    if pending:
        print(f"Pending migrations: {', '.join(pending)}", file=sys.stderr)
        return 1
    print("No pending migrations.")
    return 0


COMMANDS = {"migrate": _migrate, "version": _version, "check": _check}


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    command = argv[0] if argv else "migrate"
    handler = COMMANDS.get(command)
    if handler is None:
        print(f"Unknown command {command!r}. Known: {', '.join(COMMANDS)}", file=sys.stderr)
        return 2
    try:
        return handler()
    except MigrationError as exc:
        print(f"Migration error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - the reason is printed, not swallowed
        print(f"Could not reach the database: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
