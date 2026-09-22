"""Database engine, session lifecycle and configuration.

Deliberately synchronous SQLAlchemy. FastAPI runs ``def`` endpoints in a
threadpool, the engine's work is CPU-bound arithmetic rather than IO fan-out,
and a synchronous session is far easier to reason about and to test than an
async one. If the read path later needs async for media streaming, that is a
localised change; making everything async today would buy nothing and cost
clarity.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

DEFAULT_URL = "postgresql+psycopg://postgres@/postgres"


def database_url() -> str:
    """Connection string, from the environment.

    There is no fallback to a development default in production: a missing
    DATABASE_URL should fail loudly at start-up rather than quietly connect to
    something local and wrong.
    """
    url = os.environ.get("DATABASE_URL")
    if url:
        # Accept the plain postgres:// form that most hosting providers hand out.
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url
    if os.environ.get("GEOFATALI_ENV") == "production":
        raise RuntimeError(
            "DATABASE_URL is not set. Refusing to start in production against a "
            "default local database."
        )
    return DEFAULT_URL


_engine: Engine | None = None
_SessionFactory: sessionmaker[Session] | None = None


def engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(
            database_url(),
            pool_pre_ping=True,   # a connection killed by a restart is replaced, not raised
            future=True,
        )
    return _engine


def session_factory() -> sessionmaker[Session]:
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(bind=engine(), expire_on_commit=False, future=True)
    return _SessionFactory


def reset_engine() -> None:
    """Drop the cached engine. Used by tests that point at a different database."""
    global _engine, _SessionFactory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionFactory = None


@contextmanager
def session_scope() -> Iterator[Session]:
    """A transaction that commits on success and rolls back on any exception."""
    session = session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Iterator[Session]:
    """FastAPI dependency. One transaction per request."""
    with session_scope() as session:
        yield session
