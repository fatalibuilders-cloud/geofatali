"""Test fixtures, running against a real PostgreSQL database.

There is no SQLite stand-in and no mocked session. The schema's whole point is
the constraints it carries — an EXCLUDE over a depth range, triggers that
refuse UPDATE on an append-only table, a PostGIS column — and none of those
exist on SQLite. A test suite that passed against a database without them
would be testing a different product.

Set ``TEST_DATABASE_URL`` to a PostgreSQL instance with PostGIS available. The
suite creates its schema from the real migrations, so a passing run also proves
the migrations apply.
"""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, text

TEST_DB_ENV = "TEST_DATABASE_URL"


def _normalise(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


@pytest.fixture(scope="session")
def database_url() -> str:
    url = os.environ.get(TEST_DB_ENV)
    if not url:
        pytest.skip(
            f"{TEST_DB_ENV} is not set. The persistence suite needs a real PostgreSQL "
            "database with PostGIS — see run-tests.sh, which starts a throwaway one."
        )
    return _normalise(url)


@pytest.fixture(scope="session", autouse=True)
def migrated(database_url: str):
    """Apply the real migrations once, and prove they apply."""
    os.environ["DATABASE_URL"] = database_url
    os.environ.setdefault("JWT_SECRET", "test-only-secret-not-used-anywhere-real")

    from app.db import base
    from app.db.migrate import migrate

    base.reset_engine()
    engine = create_engine(database_url, future=True)
    # Start from nothing, so the migrations are exercised from a clean database
    # every run rather than only the first time.
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    migrate(engine)
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def clean_tables(migrated):
    """Empty the data tables between tests, keeping the schema."""
    yield
    with migrated.begin() as conn:
        conn.execute(text("SET session_replication_role = replica"))
        conn.execute(
            text(
                "TRUNCATE users, organizations, projects, boreholes, soil_layers, "
                "soil_media, ai_analyses, spt_tests, dcp_tests, cpt_tests, lab_tests, "
                "loads, calculations, foundations, reports, reviews, audit_log, "
                "usage_records RESTART IDENTITY CASCADE"
            )
        )
        conn.execute(text("SET session_replication_role = DEFAULT"))


@pytest.fixture
def client(migrated):
    from fastapi.testclient import TestClient

    from app.db import base
    from app.main import app

    base.reset_engine()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def session(migrated):
    from app.db.base import session_scope

    with session_scope() as s:
        yield s


def _unique_email(prefix: str = "user") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"


@pytest.fixture
def account(client):
    """A registered free account, with its bearer token."""
    email = _unique_email()
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "a-long-enough-passphrase", "name": "Test User"},
    )
    assert response.status_code == 201, response.text
    token = response.json()["access_token"]
    return {"email": email, "token": token, "headers": {"Authorization": f"Bearer {token}"}}


@pytest.fixture
def other_account(client):
    """A second, unrelated account — for the isolation tests."""
    email = _unique_email("other")
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "another-long-passphrase", "name": "Other User"},
    )
    assert response.status_code == 201, response.text
    token = response.json()["access_token"]
    return {"email": email, "token": token, "headers": {"Authorization": f"Bearer {token}"}}


@pytest.fixture
def engineer(client, session):
    """An engineer account with a board registration — the only kind that can approve."""
    from app.repositories import users

    email = _unique_email("engineer")
    user = users.create_user(
        session,
        email=email,
        password="engineer-long-passphrase",
        name="J. Mwangi",
        role="engineer",
        registration_no="EBK/PE/1234",
    )
    session.commit()
    response = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "engineer-long-passphrase"}
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {
        "email": email,
        "id": user.id,
        "token": token,
        "headers": {"Authorization": f"Bearer {token}"},
    }


@pytest.fixture
def project(client, account):
    response = client.post(
        "/api/v1/projects",
        json={
            "name": "Syokimau Apartments",
            "sector": "buildings_low_rise",
            "design_standard": "kebs",
            "client_name": "A. Client",
            "country": "Kenya",
            "administrative_area": "Machakos County",
            "floors": 4,
        },
        headers=account["headers"],
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def shared_org(session, account, engineer, project):
    """Put the account's project and the engineer in one organisation.

    An engineer can only review what they can see, and visibility runs through
    the organisation. Created in dependency order — the organisation first,
    then the rows that reference it — because the foreign keys are real.
    """
    from sqlalchemy import text

    org_id = session.execute(
        text("INSERT INTO organizations (name) VALUES ('Test Org') RETURNING id")
    ).scalar_one()
    session.execute(
        text("UPDATE projects SET organization_id = :o WHERE id = :p"),
        {"o": org_id, "p": project["id"]},
    )
    session.execute(
        text("UPDATE users SET organization_id = :o WHERE email IN (:a, :e)"),
        {"o": org_id, "a": account["email"], "e": engineer["email"]},
    )
    session.commit()
    return org_id
