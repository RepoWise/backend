#!/bin/bash

# OSSPREY Production Startup Script
# Launches with multiple Uvicorn workers for high performance

echo "🚀 Starting OSSPREY Backend in PRODUCTION mode..."

# Detect number of CPU cores
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

echo "📊 Detected $NUM_CORES CPU cores"
echo "⚡ Using $WORKERS Uvicorn workers"
echo ""

# Activate virtual environment
source venv/bin/activate

# Run with multiple workers
python3 -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers $WORKERS \
    --log-level info \
    --access-log \
    --proxy-headers \
    --forwarded-allow-ips='*'

echo "✅ OSSPREY Backend running on http://0.0.0.0:8000 with $WORKERS workers"
