"""The schema itself: migrations, and that the models still match it.

The SQL migrations are the source of truth. These tests make sure the ORM has
not drifted away from them, and that the runner behaves the way a migration
tool has to.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect, text

from app.db.migrate import MigrationError, applied, current_version, discover, migrate
from app.db.models import NON_MODEL_TABLES, UNMAPPED_COLUMNS, Base


class TestMigrations:
    def test_every_migration_is_recorded(self, migrated):
        recorded = applied(migrated)
        expected = {version for version, _, _ in discover()}
        assert set(recorded) == expected

    def test_running_again_is_a_no_op(self, migrated):
        assert migrate(migrated) == []

    def test_current_version_is_the_latest(self, migrated):
        assert current_version(migrated) == max(v for v, _, _ in discover())

    def test_an_edited_migration_is_refused(self, migrated, tmp_path):
        """An applied migration is history. Editing it is caught, not ignored."""
        recorded = applied(migrated)
        version = sorted(recorded)[0]
        with migrated.begin() as conn:
            conn.execute(
                text("UPDATE schema_migrations SET checksum = 'tampered' WHERE version = :v"),
                {"v": version},
            )
        with pytest.raises(MigrationError) as exc:
            migrate(migrated)
        assert "has changed since it was applied" in str(exc.value)
        # Put it back so the rest of the session is unaffected.
        with migrated.begin() as conn:
            conn.execute(
                text("UPDATE schema_migrations SET checksum = :c WHERE version = :v"),
                {"c": recorded[version], "v": version},
            )

    def test_a_badly_named_migration_is_refused(self, tmp_path):
        (tmp_path / "not-a-migration.sql").write_text("SELECT 1")
        with pytest.raises(MigrationError) as exc:
            discover(tmp_path)
        assert "NNNN_name.sql" in str(exc.value)

    def test_postgis_and_the_extensions_are_present(self, migrated):
        with migrated.connect() as conn:
            names = {
                row[0]
                for row in conn.execute(text("SELECT extname FROM pg_extension")).all()
            }
        assert {"postgis", "pgcrypto", "btree_gist"} <= names


class TestSchemaDrift:
    """The ORM and the database must describe the same thing."""

    def test_every_model_table_exists_in_the_database(self, migrated):
        actual = set(inspect(migrated).get_table_names())
        for table in Base.metadata.tables:
            assert table in actual, f"model {table} has no table in the database"

    def test_every_database_table_has_a_model(self, migrated):
        actual = set(inspect(migrated).get_table_names())
        unmapped = actual - set(Base.metadata.tables) - NON_MODEL_TABLES
        assert not unmapped, (
            f"tables with no model: {sorted(unmapped)}. Map them, or add them to "
            "NON_MODEL_TABLES with a reason."
        )

    def test_every_column_is_mapped_or_explicitly_excused(self, migrated):
        inspector = inspect(migrated)
        problems: list[str] = []
        for table_name, table in Base.metadata.tables.items():
            db_columns = {c["name"] for c in inspector.get_columns(table_name)}
            model_columns = {c.name for c in table.columns}
            excused = set(UNMAPPED_COLUMNS.get(table_name, {}))

            missing_in_model = db_columns - model_columns - excused
            missing_in_db = model_columns - db_columns
            if missing_in_model:
                problems.append(f"{table_name}: in the database but not the model: {sorted(missing_in_model)}")
            if missing_in_db:
                problems.append(f"{table_name}: in the model but not the database: {sorted(missing_in_db)}")
        assert not problems, "schema drift:\n  " + "\n  ".join(problems)

    def test_the_excused_columns_really_exist(self, migrated):
        """An excuse for a column that is gone is a stale excuse."""
        inspector = inspect(migrated)
        for table_name, excuses in UNMAPPED_COLUMNS.items():
            db_columns = {c["name"] for c in inspector.get_columns(table_name)}
            for column, reason in excuses.items():
                assert column in db_columns, f"{table_name}.{column} is excused but does not exist"
                assert reason, "an excused column needs a stated reason"

    def test_nullability_agrees(self, migrated):
        inspector = inspect(migrated)
        problems: list[str] = []
        for table_name, table in Base.metadata.tables.items():
            db_columns = {c["name"]: c for c in inspector.get_columns(table_name)}
            for column in table.columns:
                actual = db_columns.get(column.name)
                if actual is None:
                    continue
                if column.primary_key:
                    continue
                if bool(actual["nullable"]) != bool(column.nullable):
                    problems.append(
                        f"{table_name}.{column.name}: database nullable="
                        f"{actual['nullable']}, model nullable={column.nullable}"
                    )
        assert not problems, "nullability drift:\n  " + "\n  ".join(problems)


class TestHealth:
    def test_health_reports_the_schema_version(self, client):
        body = client.get("/health").json()
        assert body["status"] == "ok"
        assert body["database"]["reachable"] is True
        assert body["database"]["schema_version"]

    def test_health_is_degraded_when_the_database_is_unreachable(self, client, monkeypatch):
        """A 200 while the database is down would keep traffic flowing to nothing."""
        from app.db import base

        broken = create_engine("postgresql+psycopg://nobody@127.0.0.1:1/none", future=True)
        monkeypatch.setattr("app.main.db_engine", lambda: broken)
        body = client.get("/health").json()
        assert body["status"] == "degraded"
        assert body["database"]["reachable"] is False
        broken.dispose()
