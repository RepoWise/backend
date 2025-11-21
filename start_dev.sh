#!/bin/bash

# RepoWise Development Startup Script
# Launches with hot reload

echo "🛠️  Starting RepoWise Backend in DEVELOPMENT mode..."

# Enable hot reload by default to restart whenever files change
USE_RELOAD=${USE_RELOAD:-true}
RELOAD_DIRS=${RELOAD_DIRS:-"."}

if [ "$USE_RELOAD" = true ]; then
    echo "🌀 Hot reload enabled for development (watching: $RELOAD_DIRS)"
    RELOAD_ARGS=(--reload)

    # Support multiple comma-separated paths (e.g. ".,app")
    IFS=',' read -ra DIRS <<< "$RELOAD_DIRS"
    for dir in "${DIRS[@]}"; do
        RELOAD_ARGS+=(--reload-dir "$dir")
    done
else
    echo "ℹ️  Hot reload disabled; running without file watching"
    RELOAD_ARGS=()
fi

# Activate virtual environment
source venv/bin/activate

# Run with hot reload by default; disable with USE_RELOAD=false
python3 -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --log-level debug \
    --proxy-headers \
    --forwarded-allow-ips='*' \
    "${RELOAD_ARGS[@]}"

if [ "$USE_RELOAD" = true ]; then
    echo "✅ RepoWise Backend running on http://0.0.0.0:8000 with hot reload (watching $RELOAD_DIRS)"
else
    echo "✅ RepoWise Backend running on http://0.0.0.0:8000 without hot reload"
fi
