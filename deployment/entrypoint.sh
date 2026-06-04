#!/bin/sh
set -e

echo "Starting Backend (FastAPI)..."
echo "Listening on port ${PORT:-8080}"
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8080}"
