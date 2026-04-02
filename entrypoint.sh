#!/bin/bash
set -e

echo "Starting Django Application"

# Validate DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo "ERROR: DATABASE_URL environment variable is not set!"
    echo "Format: postgresql://user:password@host:port/database"
    exit 1
fi

# Extract database connection details from DATABASE_URL for pg_isready
# Format: postgresql://user:password@host:port/database
DB_HOST=$(echo "$DATABASE_URL" | sed -n 's/.*@\([^:]*\):.*/\1/p')
DB_PORT=$(echo "$DATABASE_URL" | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
DB_USER=$(echo "$DATABASE_URL" | sed -n 's/.*:\/\/\([^:]*\):.*/\1/p')

# Wait for database to be ready
echo "Waiting for database at ${DB_HOST}:${DB_PORT}..."
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if pg_isready -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" > /dev/null 2>&1; then
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

# Bootstrap essential data
echo "Bootstrapping essential data..."
python manage.py bootstrap_data || {
    echo "Bootstrap failed, continuing anyway..."
}

# Seed module permissions and role assignments
echo "Seeding module permissions..."
python manage.py seed_permissions || {
    echo "Permission seeding failed, continuing anyway..."
}

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput --clear || {
    echo "Static files collection failed, continuing anyway..."
}

echo "Starting Daphne server on port 8004..."
exec daphne -b 0.0.0.0 -p 8004 quidpath_backend.asgi:application
