#!/usr/bin/env bash
set -euo pipefail

# Clear any pip aliases that might route to system pip
unalias pip 2>/dev/null || true
hash -r

echo "Recreating venv to avoid externally managed environment (PEP 668)..."
rm -rf .venv
python3 -m venv .venv --upgrade-deps

echo "Upgrading packaging tools in venv..."
.venv/bin/python -m pip install -U pip setuptools wheel

echo "Installing project (editable) with venv pip..."
.venv/bin/python -m pip install -e '.[dev]'

echo "OK. Use: \n  export PYTHONPATH=src\n  .venv/bin/python -m resumetool.cli wizard"

