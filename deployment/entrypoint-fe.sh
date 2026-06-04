#!/bin/sh
set -e

echo "Starting Frontend (Streamlit)..."
echo "Listening on port ${PORT:-8080}"
exec streamlit run main.py \
    --server.port="${PORT:-8080}" \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --browser.gatherUsageStats=false
