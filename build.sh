#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

SERVICE="${1:-all}"
TAG="${TAG:-latest}"
CONTAINER_REGISTRY="${CONTAINER_REGISTRY:-${REGISTRY:-docker.io}}"
CONTAINER_NAMESPACE="${CONTAINER_NAMESPACE:-${DOCKERHUB_NAMESPACE:-${DOCKERHUB_USERNAME:-}}}"
PLATFORM="${PLATFORM:-}"
PUSH="${PUSH:-1}"

usage() {
  cat <<'EOF'
Usage:
  ./build.sh [logger|processor|all]

Environment variables:
  CONTAINER_REGISTRY   Container registry host (default: docker.io)
  CONTAINER_NAMESPACE  Registry namespace/org
  REGISTRY             Alias for CONTAINER_REGISTRY
  DOCKERHUB_NAMESPACE  Legacy Docker Hub namespace fallback
  DOCKERHUB_USERNAME   Legacy Docker Hub username fallback for namespace
  TAG                  Image tag (default: latest)
  PLATFORM             Optional docker buildx --platform value
  PUSH=0               Build locally without pushing

Examples:
  ./build.sh
  CONTAINER_NAMESPACE=myorg TAG=v1.0.0 ./build.sh logger
  CONTAINER_REGISTRY=registry.example.com CONTAINER_NAMESPACE=myteam TAG=v1.0.0 ./build.sh all
  PUSH=0 CONTAINER_NAMESPACE=myorg ./build.sh processor
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

CONTAINER_REGISTRY="${CONTAINER_REGISTRY#https://}"
CONTAINER_REGISTRY="${CONTAINER_REGISTRY#http://}"
CONTAINER_REGISTRY="${CONTAINER_REGISTRY%/}"
CONTAINER_NAMESPACE="${CONTAINER_NAMESPACE#/}"
CONTAINER_NAMESPACE="${CONTAINER_NAMESPACE%/}"
if [[ -z "$CONTAINER_REGISTRY" ]]; then
  err "CONTAINER_REGISTRY must not be empty"
fi
if [[ -z "$CONTAINER_NAMESPACE" ]]; then
  err "CONTAINER_NAMESPACE, DOCKERHUB_NAMESPACE, or DOCKERHUB_USERNAME is required"
fi

build_one() {
  local service_name="$1"
  local dockerfile_path="$2"
  local image_ref="${CONTAINER_REGISTRY}/${CONTAINER_NAMESPACE}/data-assistant-${service_name}:${TAG}"
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
