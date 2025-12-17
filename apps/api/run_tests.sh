#!/bin/bash

# Exit on error
set -e

echo "Starting backend tests..."

# Ensure we are in the api directory
cd "$(dirname "$0")"

# Check if venv exists
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate venv
source .venv/bin/activate

# Install dependencies if needed
echo "Installing test dependencies..."
pip install -r requirements.txt
pip install -r test-requirements.txt

# Run pytest
echo "Running pytest..."
pytest -v

echo "Tests completed."
