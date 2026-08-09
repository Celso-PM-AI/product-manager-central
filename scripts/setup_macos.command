#!/bin/bash

set -eu

APP_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$APP_DIR"

PYTHON_COMMAND="${PMC_PYTHON:-python3}"
if ! command -v "$PYTHON_COMMAND" >/dev/null 2>&1; then
    echo "Python was not found. Install Python 3.11 through 3.14 from python.org, then run this setup again." >&2
    exit 1
fi

PYTHON_VERSION="$($PYTHON_COMMAND -c 'import platform; print(platform.python_version())')"
if ! "$PYTHON_COMMAND" -c 'import sys; raise SystemExit(0 if (3, 11) <= sys.version_info[:2] <= (3, 14) else 1)'; then
    echo "Unsupported Python $PYTHON_VERSION. PMC requires Python 3.11 through 3.14; Python 3.14.6 is the natively validated version." >&2
    exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
    echo "Creating an isolated .venv with Python $PYTHON_VERSION..."
    if ! "$PYTHON_COMMAND" -m venv .venv; then
        echo "Virtual-environment creation failed. Confirm that this folder is writable and your Python installation includes venv." >&2
        exit 1
    fi
else
    echo "Reusing the existing local .venv."
fi
if ! ".venv/bin/python" -c 'import sys; raise SystemExit(0 if (3, 11) <= sys.version_info[:2] <= (3, 14) else 1)'; then
    echo "The existing .venv uses an unsupported Python version. Remove only this application's .venv, then run setup again." >&2
    exit 1
fi

echo "Installing PMC's declared dependencies..."
if ! ".venv/bin/python" -m pip install --disable-pip-version-check -r requirements.txt; then
    echo "Dependency installation failed. Check your internet connection and the error above, then run setup again." >&2
    exit 1
fi

echo "Setup complete. Start PMC with scripts/run_macos.command"
