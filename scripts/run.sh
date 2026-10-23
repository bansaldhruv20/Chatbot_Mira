#!/usr/bin/env bash

set -euo pipefail

# Move to the repository root.
cd "$(dirname "$0")/.."

# Start the application using the project's Python environment.
exec .venv/bin/python -m uvicorn backend.main:app \
    --host "${HOST:-127.0.0.1}" \
    --port "${PORT:-8000}"
