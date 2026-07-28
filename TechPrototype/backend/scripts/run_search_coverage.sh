#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_DIR="$(cd "$ROOT_DIR/../../UnitTest/backend/reports" && pwd)"
cd "$ROOT_DIR"

mkdir -p "$REPORT_DIR/coverage-html"

PYTHON="${PYTHON:-python}"
if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
  PYTHON="$ROOT_DIR/.venv/bin/python"
fi

"$PYTHON" -m pytest \
  tests/test_smart_search.py \
  tests/test_search_query_normalize_unit.py \
  --junitxml="$REPORT_DIR/junit-search.xml" \
  --cov=app.service.search_query_normalize \
  --cov=app.service.search_session_store \
  --cov-report=term-missing \
  --cov-report=xml:"$REPORT_DIR/coverage-search.xml" \
  --cov-report=html:"$REPORT_DIR/coverage-html" \
  --cov-fail-under=90
