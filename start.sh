#!/usr/bin/env bash
set -euo pipefail

echo "🚀 Starting Container"

# Where the repo will be on Render
APP_DIR="${APP_DIR:-/opt/render/project/src}"

if [ ! -f "$APP_DIR/manage.py" ]; then
  echo "❌ manage.py not found in $APP_DIR"
  exit 1
fi

cd "$APP_DIR"

# Load .env if present (optional, local dev)
if [ -f .env ]; then
  echo "📄 Loading .env"
  set -o allexport
  # shellcheck disable=SC1091
  source .env
  set +o allexport
fi

# Find python
PYTHON=$(command -v python3 || command -v python)
if [ -z "$PYTHON" ]; then
  echo "❌ Python not found"
  exit 1
fi
echo "🐍 Using Python at: $PYTHON"

echo "📦 Running migrations..."
$PYTHON manage.py migrate --noinput

echo "🌱 Collecting static files..."
$PYTHON manage.py collectstatic --noinput

echo "🟢 Starting Gunicorn..."
# Use DJANGO_WSGI_MODULE env var if set, else default to your project wsgi
WSGIMODULE="${DJANGO_WSGI_MODULE:-quidpath_backend.wsgi}"
exec $PYTHON -m gunicorn "${WSGIMODULE}:application" \
    --bind 0.0.0.0:${PORT:-10000} \
    --workers ${WORKERS:-3}
