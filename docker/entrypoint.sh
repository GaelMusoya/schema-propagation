#!/bin/sh
exec uvicorn schema_propagation.api:app \
    --host 0.0.0.0 \
    --port ${APP_PORT:-8000} \
    --workers ${UVICORN_WORKERS:-1} \
    --reload
