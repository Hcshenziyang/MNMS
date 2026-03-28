#!/bin/sh
set -e

python scripts/wait_for_db.py
python manage.py migrate --noinput
python scripts/build_vector_store.py
python manage.py collectstatic --noinput

exec gunicorn phoenix_project.wsgi:application --bind 0.0.0.0:8000 --workers ${GUNICORN_WORKERS:-3} --timeout ${GUNICORN_TIMEOUT:-120}