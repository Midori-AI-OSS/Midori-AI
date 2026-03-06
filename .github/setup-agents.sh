#!/usr/bin/env bash
set -euo pipefail

# Repository agent-container bootstrap.
# Assumes this script is executed from the repository root.
# It only prepares the container environment (no repo clone, no dependency install from repo files, no build/test).

_action_count=0
_next_sleep=$((3 + RANDOM % 3)) # 3-5

_sleep_jitter() {
  local s=$((5 + RANDOM % 6)) # 5-10
  sleep "$s"
}

_action() {
  _action_count=$((_action_count + 1))
  if (( _action_count >= _next_sleep )); then
    _sleep_jitter
    _action_count=0
    _next_sleep=$((3 + RANDOM % 3))
  fi
}

_is_arch_like() {
  [[ -f /etc/arch-release || -f /etc/pacman.conf ]]
}

main() {
  _action

  # PixelArch rule: if installing packages, use only `yay -Syu` form (never pacman; never plain `yay -S`).
  if _is_arch_like && command -v yay >/dev/null 2>&1; then
    if (( EUID == 0 )); then
      echo "setup-agents.sh: running as root; skipping yay installs (yay typically requires a non-root user)." >&2
      return 0
    fi

    local pkgs=()
    command -v curl >/dev/null 2>&1 || pkgs+=(curl)
    command -v jq >/dev/null 2>&1 || pkgs+=(jq)
    command -v uv >/dev/null 2>&1 || pkgs+=(uv)
    command -v bun >/dev/null 2>&1 || pkgs+=(bun)

    _action
    if (( ${#pkgs[@]} > 0 )); then
      yay -Syu --needed --noconfirm "${pkgs[@]}"
    fi
    _action
  fi
}

main "$@"
