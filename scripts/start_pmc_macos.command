#!/bin/bash

set -eu

APP_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$APP_DIR"

PYTHON_COMMAND="${PMC_PYTHON:-python3}"
VENV_PYTHON="$APP_DIR/.venv/bin/python"
NEEDS_INSTALL=0

echo "Starting Product Manager Central setup check..."

if [ ! -x "$VENV_PYTHON" ]; then
    if ! command -v "$PYTHON_COMMAND" >/dev/null 2>&1; then
        echo "Python was not found. Install Python 3.11 through 3.14 from python.org, then start PMC again." >&2
        exit 1
    fi

    PYTHON_VERSION="$($PYTHON_COMMAND -c 'import platform; print(platform.python_version())')"
    if ! "$PYTHON_COMMAND" -c 'import sys; raise SystemExit(0 if (3, 11) <= sys.version_info[:2] <= (3, 14) else 1)'; then
        echo "Unsupported Python $PYTHON_VERSION. PMC requires Python 3.11 through 3.14; Python 3.14.6 is the natively validated version." >&2
        exit 1
    fi

    echo "First start: creating PMC's isolated .venv with Python $PYTHON_VERSION..."
    if ! "$PYTHON_COMMAND" -m venv .venv; then
        echo "PMC could not create .venv. Confirm that this folder is writable and that Python includes venv, then try again." >&2
        exit 1
    fi
    NEEDS_INSTALL=1
else
    echo "Found PMC's existing .venv."
fi

if ! "$VENV_PYTHON" -c 'import sys; raise SystemExit(0 if (3, 11) <= sys.version_info[:2] <= (3, 14) else 1)'; then
    echo "PMC's existing .venv uses an unsupported Python version. Remove only this application's .venv, then start PMC again with Python 3.11 through 3.14." >&2
    exit 1
fi

if ! "$VENV_PYTHON" -c 'import docx, openai, pandas, reportlab, streamlit; from importlib.metadata import version; required={"streamlit":"1.61.1","pandas":"3.0.5","openai":"2.53.0","python-docx":"1.2.0","reportlab":"5.0.0"}; raise SystemExit(0 if all(version(name)==expected for name, expected in required.items()) else 1)' >/dev/null 2>&1; then
    NEEDS_INSTALL=1
fi

if [ "$NEEDS_INSTALL" -eq 1 ]; then
    echo "Installing PMC's pinned requirements. This can take a few minutes on the first start..."
    if ! "$VENV_PYTHON" -m pip install --disable-pip-version-check -r requirements.txt; then
        echo "PMC could not install its pinned requirements. Check the internet connection and the error above. If .venv is incomplete, remove only this application's .venv and try again." >&2
        exit 1
    fi
else
    echo "PMC's pinned runtime dependencies are available."
fi

if ! "$VENV_PYTHON" -c 'import socket; server = socket.socket(); server.bind(("127.0.0.1", 8501)); server.close()' 2>/dev/null; then
    echo "PMC cannot start because port 8501 is already in use. Stop the other local process using that port, then try again." >&2
    exit 1
fi

echo "Opening PMC at http://localhost:8501"
echo "Keep this Terminal window open. Press Control-C here to stop PMC."
exec "$VENV_PYTHON" -m streamlit run "$APP_DIR/app.py" --server.address localhost --server.port 8501 --server.headless false
