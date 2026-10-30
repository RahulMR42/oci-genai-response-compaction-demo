#!/usr/bin/env bash
# Run from any directory: /path/to/this/project/start.sh
set -euo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Use direct connections for dependency installation and OCI calls.
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy

if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
fi

if [[ ! -f .venv/.requirements-installed ]] || ! cmp -s requirements.txt .venv/.requirements-installed; then
  echo "Installing UI dependencies…"
  .venv/bin/python -m pip install -r requirements.txt
  cp requirements.txt .venv/.requirements-installed
fi

# Bind locally; forward any extra Streamlit options supplied by the caller.
exec .venv/bin/python -m streamlit run app.py \
  --server.address=127.0.0.1 \
  --server.port=8501 \
  --server.headless=true \
  --browser.gatherUsageStats=false \
  "$@"
