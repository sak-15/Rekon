#!/bin/sh
set -e

echo "=== Rekon Production Backend Starting ==="
echo "Port: ${PORT:-8000}"
echo "Running database schema migrations..."

# Run Alembic migrations automatically before starting server
alembic upgrade head

echo "Migrations completed successfully."
echo "Starting production ASGI server..."

exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --workers "${WORKERS:-4}" \
  --proxy-headers \
  --forwarded-allow-ips='*'

