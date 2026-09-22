#!/usr/bin/env sh
# Wait for the database, apply the schema, then serve.
#
# Migrations run here rather than inside the application so that starting two
# instances does not race: the migration runner takes the work in a
# transaction and records it, and a second instance finds nothing to do.
set -e

echo "GeoFatali: waiting for the database..."
for attempt in $(seq 1 30); do
  if python -m app.db.cli version >/dev/null 2>&1; then
    break
  fi
  if [ "$attempt" = "30" ]; then
    echo "GeoFatali: database still unreachable after 30 attempts. Check DATABASE_URL." >&2
    exit 1
  fi
  sleep 2
done

echo "GeoFatali: applying migrations..."
python -m app.db.cli migrate

exec uvicorn app.main:app \
  --host "${GEOFATALI_BIND_HOST:-0.0.0.0}" \
  --port "${GEOFATALI_PORT:-8000}" \
  --proxy-headers \
  --forwarded-allow-ips '*'
