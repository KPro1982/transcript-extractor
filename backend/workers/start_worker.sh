#!/bin/bash
# Start Celery worker

# Number of worker processes
WORKERS=${WORKERS_COUNT:-4}

echo "Starting Celery worker with ${WORKERS} processes..."

celery -A workers.celery_app worker \
    --loglevel=info \
    --concurrency=${WORKERS} \
    --max-tasks-per-child=50 \
    --time-limit=3600 \
    --soft-time-limit=3300








