#!/bin/bash
# Gods Platform - Temple CLI Quick Launcher
# Usage: ./temple.sh <command> [args...]

# Activate conda environment if needed
if [ -n "$CONDA_DEFAULT_ENV" ] && [ "$CONDA_DEFAULT_ENV" != "gods_env" ]; then
    echo "⚠️  Activating gods_env..."
    source $(conda info --base)/etc/profile.d/conda.sh
    conda activate gods_env
fi

# Run the CLI with all arguments
python cli/main.py "$@"
