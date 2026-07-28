#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p reports/coverage-html

.venv/bin/python -m pytest \
  tests/test_smart_search.py \
  tests/test_search_query_normalize_unit.py \
  --junitxml=reports/junit-search.xml \
  --cov=app.service.search_query_normalize \
  --cov=app.service.search_session_store \
  --cov-report=term-missing \
  --cov-report=xml:reports/coverage-search.xml \
  --cov-report=html:reports/coverage-html \
  --cov-fail-under=90
