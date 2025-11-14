#!/bin/bash

# RepoWise Development Startup Script
# Launches with hot reload

echo "🛠️  Starting RepoWise Backend in DEVELOPMENT mode..."

# Activate virtual environment
source venv/bin/activate

# Run with hot reload
python3 -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload \
    --log-level debug

echo "✅ RepoWise Backend running on http://0.0.0.0:8000 with hot reload"
