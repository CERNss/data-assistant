#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

SERVICE="${1:-all}"
TAG="${TAG:-latest}"
DOCKERHUB_NAMESPACE="${DOCKERHUB_NAMESPACE:-${DOCKERHUB_USERNAME:-}}"
PLATFORM="${PLATFORM:-}"
PUSH="${PUSH:-1}"

usage() {
  cat <<'EOF'
Usage:
  ./build.sh [logger|processor|all]

Environment variables:
  DOCKERHUB_NAMESPACE  Docker Hub namespace/org (defaults to DOCKERHUB_USERNAME)
  DOCKERHUB_USERNAME   Docker Hub username fallback for namespace
  TAG                  Image tag (default: latest)
  PLATFORM             Optional docker buildx --platform value
  PUSH=0               Build locally without pushing

Examples:
  ./build.sh
  DOCKERHUB_NAMESPACE=myorg TAG=v1.0.0 ./build.sh logger
  PUSH=0 DOCKERHUB_NAMESPACE=myorg ./build.sh processor
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

DOCKERHUB_NAMESPACE="${DOCKERHUB_NAMESPACE%/}"
if [[ -z "$DOCKERHUB_NAMESPACE" ]]; then
  err "DOCKERHUB_NAMESPACE or DOCKERHUB_USERNAME is required"
fi

build_one() {
  local service_name="$1"
  local dockerfile_path="$2"
  local image_ref="${DOCKERHUB_NAMESPACE}/data-assistant-${service_name}:${TAG}"
  local cmd=(docker buildx build -f "$dockerfile_path")

  if [[ -n "$PLATFORM" ]]; then
    cmd+=(--platform "$PLATFORM")
  fi

  cmd+=(-t "$image_ref")
  if [[ "$PUSH" == "1" ]]; then
    cmd+=(--push)
  else
    cmd+=(--load)
  fi
  cmd+=("$ROOT_DIR")

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
