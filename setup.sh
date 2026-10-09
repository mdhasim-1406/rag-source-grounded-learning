#!/usr/bin/env bash
set -euo pipefail

# Scholar Studio - Linux / macOS / WSL Setup Script
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "================================================================"
echo " Scholar Studio - Environment Setup"
echo "================================================================"

# 1. Detect Python >= 3.11 or uv
PYTHON_BIN=""
USE_UV=false

if command -v uv >/dev/null 2>&1; then
    USE_UV=true
    echo "[setup] Found uv: $(uv --version)"
fi

# Detect system python
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        if "$candidate" -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" 2>/dev/null; then
            PYTHON_BIN="$candidate"
            break
        fi
    fi
done

if [ "$USE_UV" = false ] && [ -z "$PYTHON_BIN" ]; then
    echo "[setup] ERROR: Python >= 3.11 is required, but none was found on PATH." >&2
    echo "[setup] Please install Python 3.11+ or install uv (https://astral.sh/uv)." >&2
    exit 1
fi

if [ -n "$PYTHON_BIN" ]; then
    PY_VER="$("$PYTHON_BIN" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')")"
    echo "[setup] Detected supported Python runtime: $PYTHON_BIN ($PY_VER)"
fi

# 2. Create virtual environment if not already present
VENV_DIR="$DIR/.venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "[setup] Creating virtual environment at .venv..."
    if [ "$USE_UV" = true ]; then
        uv venv "$VENV_DIR"
    else
        "$PYTHON_BIN" -m venv "$VENV_DIR"
    fi
else
    echo "[setup] Virtual environment already exists at .venv."
fi

VENV_PYTHON="$VENV_DIR/bin/python"
VENV_PIP="$VENV_DIR/bin/pip"

if [ ! -x "$VENV_PYTHON" ]; then
    echo "[setup] ERROR: Virtualenv python executable not found at $VENV_PYTHON" >&2
    exit 1
fi

# 3. Install backend package and dependencies
echo "[setup] Installing backend package and dependencies..."
if [ "$USE_UV" = true ]; then
    uv pip install --python "$VENV_PYTHON" -e "$DIR/backend"
else
    "$VENV_PIP" install -e "$DIR/backend"
fi

# 4. Copy .env.example ONLY if .env does not already exist (never overwrite secrets/database)
ENV_FILE="$DIR/.env"
ENV_EXAMPLE="$DIR/.env.example"

if [ ! -f "$ENV_FILE" ]; then
    if [ -f "$ENV_EXAMPLE" ]; then
        echo "[setup] Creating .env from .env.example with safe defaults..."
        cp "$ENV_EXAMPLE" "$ENV_FILE"
    else
        echo "[setup] WARNING: .env.example not found. Skipping .env creation."
    fi
else
    echo "[setup] Existing .env file found; preserving without changes."
fi

# 5. Ensure data storage directory exists (never touches or overwrites existing database)
mkdir -p "$DIR/data/uploads"

# 6. Verify backend package import
echo "[setup] Verifying backend installation..."
"$VENV_PYTHON" -c "import app.main; print('[setup] Verification passed: app.main loaded successfully.')"

echo "================================================================"
echo " Setup complete!"
echo " Next steps:"
echo "   1. Review or configure LLM provider settings in .env"
echo "   2. Start server: ./start.sh"
echo "================================================================"
