#!/bin/bash
# Starts SkipMan with its own Python. Used by SkipMan.app.
cd "$(dirname "$0")/.." || exit 1
exec ./.venv/bin/python main.py "$@"
