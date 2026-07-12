#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ORIGINAL_CONFIG_HOME="${XDG_CONFIG_HOME:-${HOME}/.config}"
ORIGINAL_DATA_HOME="${XDG_DATA_HOME:-${HOME}/.local/share}"
ACTION="run"
LIBRARY_ROOT="${MIDORIAI_RADIO_LIBRARY:-}"
DOWNLOADS_DIR="${MIDORIAI_DOWNLOADS_DIR:-}"
KEEP_TMP="${MIDORIAI_KEEP_TMP:-0}"
DEFAULT_RADIO_LIBRARY="${MIDORIAI_DEFAULT_RADIO_LIBRARY:-/home/lunamidori/nfs/webserver_api_files/music/}"

usage() {
  cat <<'USAGE'
Usage: ./run.sh [options]

Create an isolated one-time copy under /tmp, check dependencies, then run it.
When --library is omitted, an interactive run asks for the radio library path.

Options:
  --library PATH    Midori AI Radio library root to use for this run
  --downloads PATH  Downloads directory to use for this run
  --doctor          Set up the temporary copy and only check dependencies
  --keep-tmp        Preserve the temporary directory after exit
  -h, --help        Show this help

Environment equivalents:
  MIDORIAI_RADIO_LIBRARY, MIDORIAI_DEFAULT_RADIO_LIBRARY,
  MIDORIAI_DOWNLOADS_DIR, MIDORIAI_KEEP_TMP=1
USAGE
}

require_value() {
  if [[ $# -lt 2 || -z "$2" ]]; then
    printf 'Missing value for %s\n' "$1" >&2
    exit 64
  fi
}

default_library_root() {
  printf '%s' "$DEFAULT_RADIO_LIBRARY"
}

normalize_user_path() {
  local value="$1"
  if [[ "$value" == "~" ]]; then
    value="$HOME"
  elif [[ "$value" == "~/"* ]]; then
    value="$HOME/${value:2}"
  fi
  printf '%s' "$value"
}

prompt_for_library_root() {
  local default_root="$1"
  local response=""

  while true; do
    printf 'Midori AI Radio library [%s]: ' "$default_root" > /dev/tty
    if ! IFS= read -r response < /dev/tty; then
      printf '\nCould not read the radio library path.\n' >&2
      exit 130
    fi

    if [[ -z "$response" ]]; then
      response="$default_root"
    fi
    response="$(normalize_user_path "$response")"

    if [[ -d "$response" ]]; then
      LIBRARY_ROOT="$response"
      return
    fi

    printf 'Directory does not exist: %s\nPlease enter an existing directory.\n' "$response" > /dev/tty
  done
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --library)
      require_value "$@"
      LIBRARY_ROOT="$2"
      shift 2
      ;;
    --downloads)
      require_value "$@"
      DOWNLOADS_DIR="$2"
      shift 2
      ;;
    --doctor)
      ACTION="doctor"
      shift
      ;;
    --keep-tmp)
      KEEP_TMP=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown option: %s\n\n' "$1" >&2
      usage >&2
      exit 64
      ;;
  esac
done

if [[ ! -f "$PROJECT_DIR/build.sh" || ! -r "$PROJECT_DIR/build.sh" ]]; then
  printf 'Missing readable build helper: %s/build.sh\n' "$PROJECT_DIR" >&2
  exit 66
fi

if [[ "$ACTION" == "run" && -z "$LIBRARY_ROOT" ]]; then
  DEFAULT_LIBRARY_ROOT="$(default_library_root)"
  if [[ -r /dev/tty && -w /dev/tty ]]; then
    prompt_for_library_root "$DEFAULT_LIBRARY_ROOT"
  else
    LIBRARY_ROOT="$DEFAULT_LIBRARY_ROOT"
    printf 'No interactive terminal; using radio library: %s\n' "$LIBRARY_ROOT" >&2
  fi
fi

if [[ -n "$LIBRARY_ROOT" ]]; then
  LIBRARY_ROOT="$(normalize_user_path "$LIBRARY_ROOT")"
  if [[ ! -d "$LIBRARY_ROOT" ]]; then
    printf 'Radio library directory does not exist: %s\n' "$LIBRARY_ROOT" >&2
    exit 66
  fi
fi

if [[ -n "$DOWNLOADS_DIR" ]]; then
  DOWNLOADS_DIR="$(normalize_user_path "$DOWNLOADS_DIR")"
  if [[ ! -d "$DOWNLOADS_DIR" ]]; then
    printf 'Downloads directory does not exist: %s\n' "$DOWNLOADS_DIR" >&2
    exit 66
  fi
fi

TEMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/midoriai-radio-studio.XXXXXX")"
TEMP_PROJECT="$TEMP_ROOT/project"
TEMP_CONFIG_HOME="$TEMP_ROOT/config"
TEMP_DATA_HOME="$TEMP_ROOT/data"
TEMP_CACHE_HOME="$TEMP_ROOT/cache"

cleanup() {
  local status=$?
  trap - EXIT INT TERM
  if [[ "$KEEP_TMP" == "1" ]]; then
    printf 'Preserved one-time workspace: %s\n' "$TEMP_ROOT"
  else
    rm -rf -- "$TEMP_ROOT"
  fi
  exit "$status"
}
trap cleanup EXIT INT TERM

mkdir -p \
  "$TEMP_PROJECT" \
  "$TEMP_CONFIG_HOME" \
  "$TEMP_DATA_HOME" \
  "$TEMP_CACHE_HOME" \
  "$TEMP_ROOT/tmp"

tar \
  --exclude='./.git' \
  --exclude='./target' \
  --exclude='./build' \
  --exclude='./cmake-build-*' \
  -C "$PROJECT_DIR" \
  -cf - . | tar -C "$TEMP_PROJECT" -xf -

APP_CONFIG_DIR="$TEMP_CONFIG_HOME/midori-ai-radio-studio"
APP_DATA_DIR="$TEMP_DATA_HOME/midori-ai-radio-studio"

if [[ -d "$ORIGINAL_CONFIG_HOME/midori-ai-radio-studio" ]]; then
  cp -a "$ORIGINAL_CONFIG_HOME/midori-ai-radio-studio" "$APP_CONFIG_DIR"
fi
if [[ -d "$ORIGINAL_DATA_HOME/midori-ai-radio-studio" ]]; then
  cp -a "$ORIGINAL_DATA_HOME/midori-ai-radio-studio" "$APP_DATA_DIR"
fi

json_escape() {
  local value="$1"
  value=${value//\\/\\\\}
  value=${value//\"/\\\"}
  value=${value//$'\n'/\\n}
  value=${value//$'\r'/\\r}
  value=${value//$'\t'/\\t}
  printf '%s' "$value"
}

if [[ -n "$LIBRARY_ROOT" || -n "$DOWNLOADS_DIR" ]]; then
  if [[ -z "$LIBRARY_ROOT" ]]; then
    LIBRARY_ROOT="$(default_library_root)"
  fi
  if [[ -z "$DOWNLOADS_DIR" ]]; then
    DOWNLOADS_DIR="$HOME/Downloads"
  fi

  mkdir -p "$APP_CONFIG_DIR"
  cat > "$APP_CONFIG_DIR/settings.json" <<SETTINGS
{
  "libraryRoot": "$(json_escape "$LIBRARY_ROOT")",
  "downloadsDir": "$(json_escape "$DOWNLOADS_DIR")",
  "model": "lm-studio/qwen/qwen3.6-27b",
  "variant": "xhigh",
  "fallbackModel": "deepseek/deepseek-v4-flash",
  "fallbackVariant": "max",
  "includeBlocked": false
}
SETTINGS
fi

export XDG_CONFIG_HOME="$TEMP_CONFIG_HOME"
export XDG_DATA_HOME="$TEMP_DATA_HOME"
export XDG_CACHE_HOME="$TEMP_CACHE_HOME"
export TMPDIR="$TEMP_ROOT/tmp"

printf 'One-time workspace: %s\n' "$TEMP_ROOT"
if [[ -n "$LIBRARY_ROOT" ]]; then
  printf 'Radio library: %s\n' "$LIBRARY_ROOT"
fi
printf '\n'

bash "$TEMP_PROJECT/build.sh" doctor

if [[ "$ACTION" == "run" ]]; then
  bash "$TEMP_PROJECT/build.sh" run
fi
