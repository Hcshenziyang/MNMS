#!/bin/sh
set -e

python scripts/wait_for_services.py
alembic upgrade head
python scripts/build_vector_store.py

exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers ${UVICORN_WORKERS:-2}
