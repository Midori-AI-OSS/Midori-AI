#!/usr/bin/env bash
set -euo pipefail

export LUNA_MUSIC_ROOT="/home/midori-ai/Music/MidoriAI"  # <--- EDIT THIS PATH

export DISPLAY="${DISPLAY:-:1}"

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec uv run --directory "$script_dir" python -m gui.main
