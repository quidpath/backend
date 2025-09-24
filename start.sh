#!/bin/bash
set -e

echo "Running migrations..."
python3 manage.py migrate

echo "Collecting static files..."
python3 manage.py collectstatic --noinput

echo "Starting Gunicorn..."
gunicorn quidpath_backend.wsgi:application --bind 0.0.0.0:$PORT
