#!/usr/bin/env bash
set -euo pipefail

# Repository agent-container bootstrap.
# Assumes this script is executed from the repository root.
# It only prepares the container environment (no repo clone, no dependency install from repo files, no build/test).

main() {
  # PixelArch rule: if installing packages, use only `yay -Syu` form (never pacman; never plain `yay -S`).
  if (( EUID == 0 )); then
    echo "Running as root; skipping yay installs..." >&2
    return 0
  fi

  local pkgs=()
  command -v curl >/dev/null 2>&1 || pkgs+=(curl)
  command -v jq >/dev/null 2>&1 || pkgs+=(jq)
  command -v uv >/dev/null 2>&1 || pkgs+=(uv)
  command -v bun >/dev/null 2>&1 || pkgs+=(bun)

  if (( ${#pkgs[@]} > 0 )); then
    yay -Syu --needed --noconfirm "${pkgs[@]}"
  fi
}

main "$@"
