#!/usr/bin/env bash
set -euo pipefail

superset db upgrade
superset init
python /app/bootstrap_superset.py

gunicorn \
  --bind "0.0.0.0:${SUPERSET_PORT:-8088}" \
  --workers "${SUPERSET_WORKERS:-2}" \
  --worker-class gthread \
  --threads "${SUPERSET_THREADS:-20}" \
  --timeout "${SUPERSET_GUNICORN_TIMEOUT:-120}" \
  "superset.app:create_app()" &

python /app/mcp_server.py &

wait -n
