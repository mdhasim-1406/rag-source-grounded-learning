#!/usr/bin/env bash
set -e

# Scholar Studio - Launch Wrapper (Delegates to start.sh)
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$DIR/start.sh" "$@"
