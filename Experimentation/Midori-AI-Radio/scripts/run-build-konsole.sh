#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(cd "${script_dir}/.." && pwd)"
build_script="${project_root}/buildapk.sh"

if ! command -v konsole >/dev/null 2>&1; then
  echo "error: konsole is required but was not found in PATH" >&2
  exit 1
fi

if [ -z "${DISPLAY:-}" ] && [ -z "${WAYLAND_DISPLAY:-}" ]; then
  echo "error: no graphical display found; cannot open konsole" >&2
  exit 1
fi

if [ ! -x "${build_script}" ]; then
  chmod +x "${build_script}"
fi

konsole --hold -e bash -lc "cd '${project_root}' && ./buildapk.sh"
