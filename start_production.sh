#!/bin/bash

# RepoWise Production Startup Script
# Launches with multiple Uvicorn workers for high performance

echo "🚀 Starting RepoWise Backend in PRODUCTION mode..."

# Enable auto-reload by default so deployments pick up code changes automatically
USE_RELOAD=${USE_RELOAD:-true}

# Detect number of CPU cores for multi-worker mode
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    NUM_CORES=$(sysctl -n hw.ncpu)
else
    # Linux
    NUM_CORES=$(nproc)
fi

# Calculate optimal workers (2x cores + 1, capped at 8)
WORKERS=$((NUM_CORES * 2 + 1))
if [ $WORKERS -gt 8 ]; then
    WORKERS=8
fi

if [ "$USE_RELOAD" = true ]; then
    echo "🌀 Hot reload enabled for production deployments"
    echo "⚠️  Reload mode forces a single worker to watch for file changes"
    WORKERS=1
else
    echo "📊 Detected $NUM_CORES CPU cores"
    echo "⚡ Using $WORKERS Uvicorn workers"
fi

echo ""

# Activate virtual environment
source venv/bin/activate

# Run with hot reload by default; disable with USE_RELOAD=false
if [ "$USE_RELOAD" = true ]; then
    python3 -m uvicorn app.main:app \
        --host 0.0.0.0 \
        --port 8000 \
        --reload \
        --log-level info \
        --access-log \
        --proxy-headers \
        --forwarded-allow-ips='*'
else
    python3 -m uvicorn app.main:app \
        --host 0.0.0.0 \
        --port 8000 \
        --workers $WORKERS \
        --log-level info \
        --access-log \
        --proxy-headers \
        --forwarded-allow-ips='*'
fi

if [ "$USE_RELOAD" = true ]; then
    echo "✅ RepoWise Backend running on http://0.0.0.0:8000 with hot reload"
else
    echo "✅ RepoWise Backend running on http://0.0.0.0:8000 with $WORKERS workers"
fi
