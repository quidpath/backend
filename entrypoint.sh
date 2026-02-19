#!/bin/bash
set -e

echo "Starting Django Application"

# Wait for database to be ready
echo "Waiting for database..."
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if pg_isready -h "${DB_HOST:-db}" -p "${DB_PORT:-5432}" -U "${DB_USER:-quidpath_user}" > /dev/null 2>&1; then
        echo "Database is ready!"
        break
    fi
    echo "Database is unavailable - attempt $((RETRY_COUNT + 1))/$MAX_RETRIES"
    RETRY_COUNT=$((RETRY_COUNT + 1))
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "Database connection timeout after $MAX_RETRIES attempts"
    exit 1
fi

# Run migrations
echo "Running migrations..."
python manage.py migrate --noinput || {
    echo "Migration failed"
    exit 1
}

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput --clear || {
    echo "Static files collection failed, continuing anyway..."
}

echo "Starting Daphne server on port 8004..."
exec daphne -b 0.0.0.0 -p 8004 quidpath_backend.asgi:application
