#!/usr/bin/env bash
set -e

# Scholar Studio - Launch Script
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# 1. Ensure virtual environment is ready
VENV_DIR="$DIR/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"

if [ ! -d "$VENV_DIR" ] || [ ! -x "$VENV_PYTHON" ]; then
    echo "[start] Virtual environment not found or incomplete. Running ./setup.sh..."
    bash "$DIR/setup.sh"
fi

# 2. Prefer dedicated cross-platform launcher if present
LAUNCHER="$DIR/scripts/launcher.py"
if [ -f "$LAUNCHER" ]; then
    exec "$VENV_PYTHON" "$LAUNCHER" "$@"
fi

# 3. Fallback direct launcher if launcher.py is not available
# Load .env for HOST and PORT if set, without echoing secrets
if [ -f "$DIR/.env" ]; then
    ENV_HOST=$(grep -E '^[[:space:]]*HOST=' "$DIR/.env" | cut -d '=' -f2- | tr -d ' "\r' || true)
    ENV_PORT=$(grep -E '^[[:space:]]*PORT=' "$DIR/.env" | cut -d '=' -f2- | tr -d ' "\r' || true)
fi

HOST="${HOST:-${ENV_HOST:-127.0.0.1}}"
PORT="${PORT:-${ENV_PORT:-8000}}"

# Parse simple CLI args for fallback
while [[ $# -gt 0 ]]; do
    case "$1" in
        --host|-H)
            HOST="$2"
            shift 2
            ;;
        --port|-p)
            PORT="$2"
            shift 2
            ;;
        *)
            shift
            ;;
    esac
done

echo "================================================================"
echo " Scholar Studio - Source-Grounded Learning System"
echo "================================================================"

if [ "$HOST" = "0.0.0.0" ] || [ "$HOST" = "::" ]; then
    echo "[WARNING] Binding to 0.0.0.0 exposes Scholar Studio to your local network (LAN)."
    echo "[WARNING] This application is single-user with no built-in authentication."
    echo "[WARNING] Anyone on your local network can access the API and stored documents."
    echo "[WARNING] Ensure host firewall rules are applied. No automatic public tunnel is created."
    echo "Local Access URL:  http://127.0.0.1:${PORT}"
else
    echo "Local Access URL:  http://${HOST}:${PORT}"
fi

echo "Health Endpoint:   http://127.0.0.1:${PORT}/health"
echo "System Info:       http://127.0.0.1:${PORT}/api/v1/system"
echo "================================================================"

exec "$VENV_PYTHON" -m uvicorn app.main:app --host "$HOST" --port "$PORT"
