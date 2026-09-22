#!/usr/bin/env bash
# Run every GeoFatali test suite. Used in CI and before every commit.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "== engineering engine =="
(cd "$here/services/engineering-engine" && python3 -m pytest -q)

echo "== api =="
(cd "$here/services/api" && PYTHONPATH="$here/services/engineering-engine" python3 -m pytest tests -q)
