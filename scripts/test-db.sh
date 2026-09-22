#!/usr/bin/env bash
# Start a throwaway PostgreSQL + PostGIS instance for the test suite and print
# its connection string.
#
# The persistence tests run against a real database on purpose: the schema's
# value is in its constraints — an EXCLUDE over a depth range, triggers that
# refuse UPDATE on append-only tables, a PostGIS column — and none of those
# exist on SQLite. Testing against a substitute would test a different product.
#
#   eval "$(scripts/test-db.sh)"     # exports TEST_DATABASE_URL
#
# Requires postgresql-16 and postgresql-16-postgis-3. On Debian/Ubuntu:
#   apt-get install -y postgresql-16 postgresql-16-postgis-3
set -euo pipefail

PGBIN="${PGBIN:-/usr/lib/postgresql/16/bin}"
PGDATA="${GEOFATALI_PGDATA:-/var/lib/postgresql/gf-test}"
PGPORT="${GEOFATALI_PGPORT:-5433}"
PGSOCK="${GEOFATALI_PGSOCK:-/tmp}"
DBNAME=geofatali_test

if [ ! -x "$PGBIN/pg_ctl" ]; then
  echo "PostgreSQL 16 not found at $PGBIN. Set PGBIN, or install postgresql-16." >&2
  exit 1
fi

# Already up? Reuse it — re-initialising on every run wastes ten seconds a time.
if su postgres -c "$PGBIN/pg_isready -h $PGSOCK -p $PGPORT" >/dev/null 2>&1; then
  :
else
  rm -rf "$PGDATA"
  install -d -o postgres -g postgres "$PGDATA"
  su postgres -c "$PGBIN/initdb -D $PGDATA -A trust -U postgres" >/dev/null
  su postgres -c "$PGBIN/pg_ctl -D $PGDATA -o '-p $PGPORT -k $PGSOCK' -l $PGDATA/server.log -w start" >/dev/null
fi

if ! su postgres -c "$PGBIN/psql -h $PGSOCK -p $PGPORT -U postgres -lqt" | cut -d'|' -f1 | grep -qw "$DBNAME"; then
  su postgres -c "$PGBIN/createdb -h $PGSOCK -p $PGPORT -U postgres $DBNAME"
fi

# The suite applies the migrations itself, from a clean schema, so a passing
# run also proves the migrations apply.
echo "export TEST_DATABASE_URL='postgresql+psycopg://postgres@/$DBNAME?host=$PGSOCK&port=$PGPORT'"
