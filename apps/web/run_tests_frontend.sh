#!/bin/bash

# Exit on error
set -e

echo "Starting frontend tests..."

# Ensure we are in the web directory
cd "$(dirname "$0")"

# Install dev dependencies if needed
# We use pnpm add -D (assuming pnpm usage based on pnpm-lock.yaml presence)
if ! grep -q "vitest" package.json; then
    echo "Installing test dependencies (vitest, testing-library)..."
    # Note: In a real environment, you'd want to be careful not to modify package.json 
    # without user intent, but this script is explicitly for setting up the test environment.
    pnpm add -D vitest @vitejs/plugin-react jsdom @testing-library/react @testing-library/jest-dom
fi

# Run vitest
echo "Running vitest..."
npx vitest run

echo "Frontend tests completed."
