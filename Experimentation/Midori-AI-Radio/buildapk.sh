#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Midori AI: build Midori AI Radio Android APKs

Usage:
  buildapk.sh [--help]

Output directory:
  Experimentation/Midori-AI-Radio/target/<YYYYMMDD-HHMMSS>/
  If a folder already exists for the same second, a numeric suffix is added.

Examples:
  ./buildapk.sh
  # Example output: Experimentation/Midori-AI-Radio/target/20260226-153045/
EOF
}

die() {
  echo "error: $*" >&2
  exit 1
}

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if git -C "${script_dir}" rev-parse --show-toplevel >/dev/null 2>&1; then
  repo_root="$(git -C "${script_dir}" rev-parse --show-toplevel)"
else
  repo_root="$(cd "${script_dir}/../.." && pwd)"
fi

while [ "$#" -gt 0 ]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown argument: $1 (try --help)"
      ;;
  esac
  shift
done

command -v docker >/dev/null 2>&1 || die "docker is required but was not found in PATH"

if ! docker info >/dev/null 2>&1; then
  die "docker daemon not running or not accessible (ensure the docker service is running and you can access /var/run/docker.sock)"
fi

project_dir="${repo_root}/Experimentation/Midori-AI-Radio"
[ -d "${project_dir}" ] || die "Android project not found: ${project_dir}"

target_root="${project_dir}/target"
timestamp="$(date +%Y%m%d-%H%M%S)"
out_dir="${target_root}/${timestamp}"
suffix=1
while [ -e "${out_dir}" ]; do
  out_dir="${target_root}/${timestamp}-${suffix}"
  suffix=$((suffix + 1))
done

mkdir -p "${out_dir}"
chmod -R a+rwx "${out_dir}" >/dev/null 2>&1 || true
out_dir="$(cd "${out_dir}" && pwd)"

dockerfile_path="${script_dir}/dockerfile"
[ -f "${dockerfile_path}" ] || die "Dockerfile not found: ${dockerfile_path}"

image_tag="pixelarch-midoriai-radio-android-apk:local"

echo "build-midoriai-radio-apk: repo_root=${repo_root}"
echo "build-midoriai-radio-apk: out_dir=${out_dir}"
echo "build-midoriai-radio-apk: dockerfile=${dockerfile_path}"
echo "build-midoriai-radio-apk: image_tag=${image_tag}"

# Build the image.
docker build \
  -f "${dockerfile_path}" \
  -t "${image_tag}" \
  "${script_dir}"

# Run the build in a container.
docker run --rm \
  -v "${repo_root}:/workspace" \
  -v "${out_dir}:/out" \
  -w "/workspace/Experimentation/Midori-AI-Radio" \
  "${image_tag}" \
  bash -lc 'set -euo pipefail
chmod +x ./gradlew
./gradlew :app:assembleDebug

if [ -d "app/build/outputs/apk" ]; then
  find app/build/outputs/apk -type f -name "*.apk" -print -exec cp -f {} /out/ \;
fi'

apk_count="$(find "${out_dir}" -maxdepth 1 -type f -name "*.apk" | wc -l | tr -d ' ')"
if [ "${apk_count}" -lt 1 ]; then
  die "no APKs were produced (expected *.apk in ${out_dir})"
fi

echo "build-midoriai-radio-apk: produced ${apk_count} APK(s) in ${out_dir}"

command -v adb >/dev/null 2>&1 || die "adb is required for install but was not found in PATH"

install_apk="$(find "${out_dir}" -maxdepth 1 -type f -name "*debug*.apk" | head -n 1)"
if [ -z "${install_apk}" ]; then
  install_apk="$(find "${out_dir}" -maxdepth 1 -type f -name "*.apk" | head -n 1)"
fi

[ -n "${install_apk}" ] || die "could not resolve an APK to install from ${out_dir}"

echo "build-midoriai-radio-apk: uninstalling xyz.midoriai.radio (no-fail)"
adb uninstall xyz.midoriai.radio >/dev/null 2>&1 || true

echo "build-midoriai-radio-apk: installing ${install_apk}"
adb install -r "${install_apk}"
