#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[cleanup] removing pytest/cache artifacts"
rm -rf .pytest_cache __pycache__
find . -type d -name "__pycache__" -prune -exec rm -rf {} +
find . -type f -name "*.pyc" -delete

echo "[cleanup] removing ephemeral reports/experiments outputs"
rm -rf reports/* experiments/*

echo "[cleanup] removing unit/test project sandboxes only"
find projects -maxdepth 1 -type d \( -name 'test_*' -o -name 'unit_*' \) -prune -exec rm -rf {} +

echo "[cleanup] done"
