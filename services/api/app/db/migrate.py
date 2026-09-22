"""A small versioned migration runner.

Alembic autogeneration is a poor fit here. The schema is hand-written SQL
because it carries constraints, triggers and EXCLUDE clauses that express
engineering rules, and those are exactly the things autogeneration mangles or
silently drops. So migrations stay as numbered .sql files, applied in order
and recorded — which is all a migration tool has to do.

Each file runs inside its own transaction. A file that fails leaves nothing
behind and is not recorded, so re-running after a fix is safe.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Engine

MIGRATIONS_DIR = Path(__file__).resolve().parents[4] / "database" / "migrations"

_FILENAME = re.compile(r"^(\d{4})_([a-z0-9_]+)\.sql$")

_SCHEMA_MIGRATIONS = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    checksum    TEXT NOT NULL,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""


class MigrationError(RuntimeError):
    pass


def discover(directory: Path | None = None) -> list[tuple[str, str, Path]]:
    """Every migration file, in version order."""
    directory = directory or MIGRATIONS_DIR
    if not directory.is_dir():
        raise MigrationError(f"No migrations directory at {directory}")
    found: list[tuple[str, str, Path]] = []
    for path in sorted(directory.iterdir()):
        if path.suffix != ".sql":
            continue
        match = _FILENAME.match(path.name)
        if not match:
            raise MigrationError(
                f"{path.name} does not match the NNNN_name.sql convention, so its "
                "position in the sequence is ambiguous. Rename it."
            )
        found.append((match.group(1), match.group(2), path))
    versions = [v for v, _, _ in found]
    if len(set(versions)) != len(versions):
        raise MigrationError(f"Duplicate migration version numbers: {versions}")
    return found


def _checksum(sql: str) -> str:
    return hashlib.sha256(sql.encode("utf-8")).hexdigest()[:16]


def applied(engine: Engine) -> dict[str, str]:
    with engine.begin() as conn:
        conn.execute(text(_SCHEMA_MIGRATIONS))
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT version, checksum FROM schema_migrations")).all()
    return {row[0]: row[1] for row in rows}


def migrate(engine: Engine, directory: Path | None = None) -> list[str]:
    """Apply every migration not yet applied. Returns the versions run."""
    already = applied(engine)
    run: list[str] = []
    for version, name, path in discover(directory):
        sql = path.read_text()
        checksum = _checksum(sql)
        if version in already:
            if already[version] != checksum:
                raise MigrationError(
                    f"Migration {version}_{name}.sql has changed since it was applied "
                    f"(recorded {already[version]}, now {checksum}). An applied "
                    "migration is history and must not be edited — add a new one."
                )
            continue
        with engine.begin() as conn:
            conn.execute(text(sql))
            conn.execute(
                text(
                    "INSERT INTO schema_migrations (version, name, checksum) "
                    "VALUES (:v, :n, :c)"
                ),
                {"v": version, "n": name, "c": checksum},
            )
        run.append(version)
    return run


def current_version(engine: Engine) -> str | None:
    versions = sorted(applied(engine))
    return versions[-1] if versions else None
