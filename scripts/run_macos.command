#!/bin/bash

set -eu

APP_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$APP_DIR"
VENV_PYTHON="$APP_DIR/.venv/bin/python"

if [ ! -x "$VENV_PYTHON" ]; then
    echo "PMC is not set up. Run scripts/setup_macos.command first." >&2
    exit 1
fi
if ! "$VENV_PYTHON" -c 'import sys; raise SystemExit(0 if (3, 11) <= sys.version_info[:2] <= (3, 14) else 1)'; then
    echo "The PMC virtual environment uses an unsupported Python version. Remove .venv and run scripts/setup_macos.command again with Python 3.11 through 3.14." >&2
    exit 1
fi
if ! "$VENV_PYTHON" -c 'import docx, openai, pandas, reportlab, streamlit'; then
    echo "PMC dependencies are missing or incomplete. Run scripts/setup_macos.command again." >&2
    exit 1
fi

echo "Starting Product Manager Central. Press Control-C in this window to stop."
exec "$VENV_PYTHON" -m streamlit run "$APP_DIR/app.py" --server.address localhost --server.port 8501 --server.headless false
