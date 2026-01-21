#!/bin/bash

# Exit on error
set -e

echo "Starting backend tests..."

# Ensure we are in the api directory
cd "$(dirname "$0")"

# Sync dependencies with uv
echo "Syncing test dependencies with uv..."
uv sync --frozen --extra test --no-install-project

# Run pytest
echo "Running pytest..."
.venv/bin/pytest -v

echo "Tests completed."
