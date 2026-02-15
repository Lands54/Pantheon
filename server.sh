#!/bin/bash
# Gods Platform - Server Quick Launcher
# Usage: ./server.sh

# Activate conda environment if needed
if [ -n "$CONDA_DEFAULT_ENV" ] && [ "$CONDA_DEFAULT_ENV" != "gods_env" ]; then
    echo "⚠️  Activating gods_env..."
    source $(conda info --base)/etc/profile.d/conda.sh
    conda activate gods_env
fi

echo "🚀 Starting Gods Platform API Server..."
echo "📍 Server will be available at: http://localhost:8000"
echo "📖 API docs at: http://localhost:8000/docs"
echo ""

# Run the server
python server.py
