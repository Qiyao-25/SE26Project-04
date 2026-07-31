#!/usr/bin/env sh
set -eu

if [ -n "${PAPERMATE_DB_PASSWORD:-}" ]; then
    encoded_password=$(python -c 'import os; from urllib.parse import quote; print(quote(os.environ["PAPERMATE_DB_PASSWORD"], safe=""))')
    export PAPERMATE_DATABASE_URL="postgresql+psycopg://papermate:${encoded_password}@db:5432/papermate"
fi

python -m alembic upgrade head
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
