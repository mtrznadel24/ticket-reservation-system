#!/bin/sh
set -e

cd /app

while ! nc -z db 5432; do
  sleep 0.2
done

if [ "$1" = "gunicorn" ]; then
    python manage.py migrate --noinput
    python manage.py collectstatic --noinput
    echo "Tworzę superużytkownika..."
    python manage.py createsuperuser --noinput || echo "Superuser already exists"
fi

exec "$@"


