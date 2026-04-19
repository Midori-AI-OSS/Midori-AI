#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

exec uv run --project "$SCRIPT_DIR" python "$SCRIPT_DIR/server.py"
