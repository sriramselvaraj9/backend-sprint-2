#!/usr/bin/env sh
set -e

echo "================================================================="
echo "   Film Review Platform - Startup & Safety Gate Enforcement     "
echo "================================================================="

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Run all pre-deployment safety gates using the deployed shared-pre-deployment package
python "$SCRIPT_DIR/pre_deploy.py"

# Database migrations and seed
echo ""
echo "[STARTUP] Applying schema migrations and seeding..."
alembic upgrade head
python seed.py
echo "[PASS] Database schema and seed complete."

# Start FastAPI server
echo ""
echo "[STARTUP] All safety gates passed! Starting FastAPI server..."
echo "================================================================="

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

if [ $# -gt 0 ]; then
    if [ "$1" = "uvicorn" ] && [ "$2" = "app.main:app" ] && [ $# -eq 2 ]; then
        exec uvicorn app.main:app --host "$HOST" --port "$PORT"
    fi
    exec "$@"
else
    exec uvicorn app.main:app --host "$HOST" --port "$PORT"
fi
