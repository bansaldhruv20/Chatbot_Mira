#!/usr/bin/env bash

set -euo pipefail

cd "$(dirname "$0")/.."

if command -v uv >/dev/null 2>&1; then
    export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/mira-uv-cache}"

    uv venv --allow-existing .venv

    uv pip sync \
        --python .venv/bin/python \
        requirements.lock
else
    python3 -m venv .venv

    PIP_CACHE_DIR="${PIP_CACHE_DIR:-/tmp/mira-pip-cache}" \
        .venv/bin/python -m pip install \
        -r requirements.lock
fi
