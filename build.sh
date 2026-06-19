#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

SERVICE="${1:-all}"
TAG="${TAG:-latest}"
REGISTRY="${REGISTRY:-192.168.10.142:5000}"
PLATFORM="${PLATFORM:-}"

usage() {
  cat <<'EOF'
Usage:
  ./build.sh [logger|processor|all]

Environment variables:
  TAG        Image tag (default: latest)
  REGISTRY   Registry host/path (default: 192.168.10.142:5000)
  PLATFORM   Optional docker buildx --platform value

Examples:
  ./build.sh
  TAG=v1.0.0 ./build.sh logger
  REGISTRY=192.168.10.142:5000 ./build.sh processor
EOF
}

err() {
  echo "[build.sh] $*" >&2
  exit 1
}

if [[ "$SERVICE" == "-h" || "$SERVICE" == "--help" ]]; then
  usage
  exit 0
fi

case "$SERVICE" in
  logger|processor|all)
    ;;
  *)
    usage >&2
    err "Invalid service: $SERVICE"
    ;;
esac

command -v docker >/dev/null 2>&1 || err "docker command not found"
docker buildx version >/dev/null 2>&1 || err "docker buildx is required but was not found"

REGISTRY="${REGISTRY%/}"

build_one() {
  local service_name="$1"
  local dockerfile_path="$2"
  local image_ref="${REGISTRY}/data-assistant-${service_name}:${TAG}"
  local cmd=(docker buildx build -f "$dockerfile_path")

  if [[ -n "$PLATFORM" ]]; then
    cmd+=(--platform "$PLATFORM")
  fi

  cmd+=(-t "$image_ref" --push "$ROOT_DIR")

  printf '[build.sh] Building %s as %s with command:\n' "$service_name" "$image_ref"
  printf '  %q' "${cmd[@]}"
  printf '\n'

  "${cmd[@]}"
}

if [[ "$SERVICE" == "logger" || "$SERVICE" == "all" ]]; then
  build_one "logger" "$ROOT_DIR/logger_service/Dockerfile"
fi

if [[ "$SERVICE" == "processor" || "$SERVICE" == "all" ]]; then
  build_one "processor" "$ROOT_DIR/processor_service/Dockerfile"
fi

printf '[build.sh] Done.\n'
