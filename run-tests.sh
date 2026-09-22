#!/usr/bin/env bash
# Run every GeoFatali test suite.
#
# The engine suite is pure Python and runs anywhere. The API suite needs a real
# PostgreSQL database; if TEST_DATABASE_URL is not set, this script tries to
# start a throwaway one, and the persistence tests skip with a clear reason if
# that is not possible.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "== engineering engine =="
(cd "$here/services/engineering-engine" && python3 -m pytest -q)

if [ -z "${TEST_DATABASE_URL:-}" ]; then
  if eval "$("$here/scripts/test-db.sh" 2>/dev/null)"; then
    echo "-- started a throwaway PostgreSQL for the persistence tests"
  else
    echo "-- no PostgreSQL available; persistence tests will skip" >&2
  fi
fi

echo "== api =="
(cd "$here/services/api" && PYTHONPATH="$here/services/engineering-engine" python3 -m pytest -q)
