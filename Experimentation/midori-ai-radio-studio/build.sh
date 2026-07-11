#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CACHE_ROOT="${XDG_CACHE_HOME:-${HOME}/.cache}/midori-ai-radio-studio"
TARGET_DIR="${CACHE_ROOT}/target"
PROFILE="release"
BINARY="${TARGET_DIR}/${PROFILE}/midori-ai-radio-studio"
ACTION="${1:-build}"

print_arch_dependencies() {
  cat <<'DEPS'
Arch Linux / KDE dependency command:
  sudo pacman -S --needed base-devel rust cargo qt6-base qt6-declarative qt6-wayland kirigami qqc2-desktop-style ffmpeg mpv

OpenCode is optional for metadata management, but required for model-generated drafts:
  https://opencode.ai
DEPS
}

require_command() {
  local command_name="$1"
  if ! command -v "$command_name" >/dev/null 2>&1; then
    printf 'Missing required command: %s\n\n' "$command_name" >&2
    print_arch_dependencies >&2
    exit 127
  fi
}

doctor() {
  local failed=0
  printf 'Midori AI Radio Studio build doctor\n'
  printf 'Project: %s\n' "$PROJECT_DIR"
  printf 'Build cache: %s\n\n' "$TARGET_DIR"

  for command_name in cargo rustc c++ pkg-config ffmpeg ffprobe; do
    if command -v "$command_name" >/dev/null 2>&1; then
      printf '[ok]      %s\n' "$command_name"
    else
      printf '[missing] %s\n' "$command_name"
      failed=1
    fi
  done

  if command -v opencode >/dev/null 2>&1; then
    printf '[ok]      opencode (prompt generation enabled)\n'
  else
    printf '[optional] opencode is absent; the GUI and local prompt-learning fallback still work\n'
  fi

  if pkg-config --exists Qt6Core Qt6Gui Qt6Qml Qt6Quick 2>/dev/null; then
    printf '[ok]      Qt 6 development packages\n'
  else
    printf '[missing] Qt 6 development packages were not found by pkg-config\n'
    failed=1
  fi

  printf '\n'
  print_arch_dependencies
  return "$failed"
}

build() {
  require_command cargo
  require_command c++
  mkdir -p "$TARGET_DIR"
  printf 'Building Midori AI Radio Studio outside the monorepo…\n'
  (
    cd "$PROJECT_DIR"
    CARGO_TARGET_DIR="$TARGET_DIR" cargo build --release
  )
  printf '\nBuilt: %s\n' "$BINARY"
}

run_app() {
  if [[ ! -x "$BINARY" ]]; then
    build
  fi
  exec "$BINARY"
}

install_app() {
  build
  local bin_dir="${HOME}/.local/bin"
  local applications_dir="${XDG_DATA_HOME:-${HOME}/.local/share}/applications"
  local metainfo_dir="${XDG_DATA_HOME:-${HOME}/.local/share}/metainfo"

  install -d "$bin_dir" "$applications_dir" "$metainfo_dir"
  install -m 0755 "$BINARY" "$bin_dir/midori-ai-radio-studio"
  install -m 0644 "$PROJECT_DIR/packaging/org.midoriai.RadioStudio.desktop" "$applications_dir/"
  install -m 0644 "$PROJECT_DIR/packaging/org.midoriai.RadioStudio.metainfo.xml" "$metainfo_dir/"

  if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$applications_dir" >/dev/null 2>&1 || true
  fi

  printf 'Installed Midori AI Radio Studio for the current user.\n'
  printf 'Binary: %s/midori-ai-radio-studio\n' "$bin_dir"
}

clean() {
  if [[ -d "$CACHE_ROOT" ]]; then
    rm -rf -- "$CACHE_ROOT"
    printf 'Removed build cache: %s\n' "$CACHE_ROOT"
  else
    printf 'Build cache is already clean.\n'
  fi
}

case "$ACTION" in
  build)
    build
    ;;
  run)
    run_app
    ;;
  install)
    install_app
    ;;
  doctor)
    doctor
    ;;
  clean)
    clean
    ;;
  *)
    printf 'Usage: %s [build|run|install|doctor|clean]\n' "$0" >&2
    exit 64
    ;;
esac
