#!/usr/bin/env bash
set -euo pipefail

echo "🚀 Starting Container"

# Detect manage.py directory automatically
APP_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ ! -f "$APP_DIR/manage.py" ]; then
  echo "❌ manage.py not found in $APP_DIR"
  echo "👉 Set APP_DIR correctly inside start.sh"
  exit 1
fi

cd "$APP_DIR"

# Load environment variables from .env if present
if [ -f .env ]; then
  echo "📄 Loading environment variables from .env"
  set -o allexport
  source .env
  set +o allexport
fi

# Pick the best python available
PYTHON=$(command -v python3 || command -v python)

if [ -z "$PYTHON" ]; then
  echo "❌ No Python interpreter found in PATH"
  exit 1
fi

echo "🐍 Using Python at: $PYTHON"

echo "📦 Running migrations..."
$PYTHON manage.py migrate --noinput

echo "🌱 Collecting static files..."
$PYTHON manage.py collectstatic --noinput

echo "🟢 Starting Gunicorn server..."
exec $PYTHON -m gunicorn "${DJANGO_WSGI_MODULE:-quidpath_backend.wsgi}:application" \
    --bind 0.0.0.0:${PORT:-8000} \
    --workers ${WORKERS:-3}
