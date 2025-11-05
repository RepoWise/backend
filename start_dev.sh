#!/bin/bash

# OSSPREY Development Startup Script
# Launches with hot reload

echo "🛠️  Starting OSSPREY Backend in DEVELOPMENT mode..."

# Activate virtual environment
source venv/bin/activate

# Run with hot reload
python3 -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload \
    --log-level debug

echo "✅ OSSPREY Backend running on http://0.0.0.0:8000 with hot reload"
