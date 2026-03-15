#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

SERVICE="${SERVICE:-all}"
TAG="${TAG:-latest}"
IMAGE_PREFIX="${IMAGE_PREFIX:-data-assistant}"
CONTEXT="${CONTEXT:-$ROOT_DIR}"

LOGGER_DOCKERFILE="${LOGGER_DOCKERFILE:-$ROOT_DIR/logger_service/Dockerfile}"
PROCESSOR_DOCKERFILE="${PROCESSOR_DOCKERFILE:-$ROOT_DIR/processor_service/Dockerfile}"

LOGGER_IMAGE="${LOGGER_IMAGE:-${IMAGE_PREFIX}-logger}"
PROCESSOR_IMAGE="${PROCESSOR_IMAGE:-${IMAGE_PREFIX}-processor}"

PLATFORM="${PLATFORM:-}"
TARGET="${TARGET:-}"

NO_CACHE=0
PULL=0
PUSH=0
DRY_RUN=0

BUILD_ARGS=()

usage() {
  cat <<'EOF'
Usage:
  ./build.sh [service] [options]

Services:
  logger | processor | all (default: all)

Options:
  -s, --service <name>           Build service: logger|processor|all
  -t, --tag <tag>                Image tag (default: latest)
  -p, --image-prefix <prefix>    Prefix for default image names (default: data-assistant)
      --logger-image <ref>       Override logger image name/ref
      --processor-image <ref>    Override processor image name/ref
      --logger-dockerfile <path> Override logger Dockerfile path
      --processor-dockerfile <path>
                                 Override processor Dockerfile path
      --context <path>           Build context path (default: script root)
      --platform <value>         docker build --platform value
      --target <stage>           docker build --target stage
      --build-arg KEY=VALUE      Build arg (repeatable)
      --no-cache                 Build without cache
      --pull                     Always attempt to pull newer base images
      --push                     Push image after successful build
      --dry-run                  Print command(s) only
  -h, --help                     Show this help

Examples:
  ./build.sh
  ./build.sh logger --tag v1.0.0
  ./build.sh -s all --tag dev --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
  ./build.sh processor --processor-image registry.example.com/da-processor:2026.03 --push

Environment variable defaults:
  SERVICE, TAG, IMAGE_PREFIX, CONTEXT
  LOGGER_DOCKERFILE, PROCESSOR_DOCKERFILE
  LOGGER_IMAGE, PROCESSOR_IMAGE
  PLATFORM, TARGET
EOF
}

err() {
  echo "[build.sh] $*" >&2
  exit 1
}

require_value() {
  local option_name="$1"
  local option_value="${2:-}"
  [[ -n "$option_value" ]] || err "Missing value for $option_name"
}

has_tag_or_digest() {
  local ref="$1"
  [[ "$ref" == *@* ]] && return 0

  local last_segment="${ref##*/}"
  [[ "$last_segment" == *:* ]]
}

with_default_tag() {
  local ref="$1"
  if has_tag_or_digest "$ref"; then
    printf '%s' "$ref"
  else
    printf '%s:%s' "$ref" "$TAG"
  fi
}

if [[ $# -gt 0 && "$1" != -* ]]; then
  SERVICE="$1"
  shift
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    -s|--service)
      require_value "$1" "${2:-}"
      SERVICE="$2"
      shift 2
      ;;
    -t|--tag)
      require_value "$1" "${2:-}"
      TAG="$2"
      shift 2
      ;;
    -p|--image-prefix)
      require_value "$1" "${2:-}"
      IMAGE_PREFIX="$2"
      LOGGER_IMAGE="${IMAGE_PREFIX}-logger"
      PROCESSOR_IMAGE="${IMAGE_PREFIX}-processor"
      shift 2
      ;;
    --logger-image)
      require_value "$1" "${2:-}"
      LOGGER_IMAGE="$2"
      shift 2
      ;;
    --processor-image)
      require_value "$1" "${2:-}"
      PROCESSOR_IMAGE="$2"
      shift 2
      ;;
    --logger-dockerfile)
      require_value "$1" "${2:-}"
      LOGGER_DOCKERFILE="$2"
      shift 2
      ;;
    --processor-dockerfile)
      require_value "$1" "${2:-}"
      PROCESSOR_DOCKERFILE="$2"
      shift 2
      ;;
    --context)
      require_value "$1" "${2:-}"
      CONTEXT="$2"
      shift 2
      ;;
    --platform)
      require_value "$1" "${2:-}"
      PLATFORM="$2"
      shift 2
      ;;
    --target)
      require_value "$1" "${2:-}"
      TARGET="$2"
      shift 2
      ;;
    --build-arg)
      require_value "$1" "${2:-}"
      BUILD_ARGS+=("$2")
      shift 2
      ;;
    --build-arg=*)
      BUILD_ARGS+=("${1#*=}")
      shift
      ;;
    --no-cache)
      NO_CACHE=1
      shift
      ;;
    --pull)
      PULL=1
      shift
      ;;
    --push)
      PUSH=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      err "Unknown option: $1"
      ;;
  esac
done

case "$SERVICE" in
  logger|processor|all)
    ;;
  *)
    err "Invalid service: $SERVICE (expected logger|processor|all)"
    ;;
esac

command -v docker >/dev/null 2>&1 || err "docker command not found"

[[ -f "$LOGGER_DOCKERFILE" ]] || err "Logger Dockerfile not found: $LOGGER_DOCKERFILE"
[[ -f "$PROCESSOR_DOCKERFILE" ]] || err "Processor Dockerfile not found: $PROCESSOR_DOCKERFILE"
[[ -d "$CONTEXT" ]] || err "Build context path not found: $CONTEXT"

build_one() {
  local service_name="$1"
  local dockerfile_path="$2"
  local image_ref="$3"

  local cmd=(docker build -f "$dockerfile_path" -t "$image_ref")

  if [[ -n "$PLATFORM" ]]; then
    cmd+=(--platform "$PLATFORM")
  fi
  if [[ -n "$TARGET" ]]; then
    cmd+=(--target "$TARGET")
  fi
  if [[ "$NO_CACHE" -eq 1 ]]; then
    cmd+=(--no-cache)
  fi
  if [[ "$PULL" -eq 1 ]]; then
    cmd+=(--pull)
  fi

  if [[ ${#BUILD_ARGS[@]} -gt 0 ]]; then
    local arg
    for arg in "${BUILD_ARGS[@]}"; do
      cmd+=(--build-arg "$arg")
    done
  fi

  cmd+=("$CONTEXT")

  printf '[build.sh] Building %s with command:\n' "$service_name"
  printf '  %q' "${cmd[@]}"
  printf '\n'

  if [[ "$DRY_RUN" -eq 0 ]]; then
    "${cmd[@]}"
  fi

  if [[ "$PUSH" -eq 1 ]]; then
    printf '[build.sh] Pushing %s\n' "$image_ref"
    if [[ "$DRY_RUN" -eq 0 ]]; then
      docker push "$image_ref"
    fi
  fi
}

LOGGER_REF="$(with_default_tag "$LOGGER_IMAGE")"
PROCESSOR_REF="$(with_default_tag "$PROCESSOR_IMAGE")"

if [[ "$SERVICE" == "logger" || "$SERVICE" == "all" ]]; then
  build_one "logger" "$LOGGER_DOCKERFILE" "$LOGGER_REF"
fi

if [[ "$SERVICE" == "processor" || "$SERVICE" == "all" ]]; then
  build_one "processor" "$PROCESSOR_DOCKERFILE" "$PROCESSOR_REF"
fi

printf '[build.sh] Done.\n'
