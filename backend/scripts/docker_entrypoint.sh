#!/usr/bin/env bash
set -euo pipefail
python -m alembic upgrade head
# Optional extra uvicorn flags (e.g. --workers 4 --no-access-log for production).
# shellcheck disable=SC2086
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" ${UVICORN_EXTRA_ARGS:-}
