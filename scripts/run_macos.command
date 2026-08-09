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
if ! "$VENV_PYTHON" -c 'import openai, pandas, streamlit'; then
    echo "PMC dependencies are missing or incomplete. Run scripts/setup_macos.command again." >&2
    exit 1
fi

SESSION_KEY_ADDED=0
if [ -z "${OPENAI_API_KEY:-}" ] && [ -t 0 ]; then
    read -r -p "Configure the optional OpenAI API key for this terminal session? [y/N] " KEY_CHOICE
    case "$KEY_CHOICE" in
        y|Y)
            read -r -s -p "OpenAI API key (input hidden): " OPENAI_API_KEY
            echo
            if [ -n "$OPENAI_API_KEY" ]; then
                export OPENAI_API_KEY
                SESSION_KEY_ADDED=1
            fi
            ;;
    esac
fi

cleanup_session_key() {
    if [ "$SESSION_KEY_ADDED" -eq 1 ]; then
        unset OPENAI_API_KEY
    fi
}
trap cleanup_session_key EXIT INT TERM

echo "Starting Product Manager Central. Press Control-C in this window to stop."
"$VENV_PYTHON" -m streamlit run "$APP_DIR/app.py"
