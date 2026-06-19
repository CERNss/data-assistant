#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

DATA_ROOT="${DATA_ROOT:-$ROOT_DIR/.data}"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env}"
ENV_EXAMPLE="${ENV_EXAMPLE:-$ROOT_DIR/.env.example}"
CONTAINER_REGISTRY_ENV_SET=0
CONTAINER_NAMESPACE_ENV_SET=0
IMAGE_TAG_ENV_SET=0
TAGGER_BASE_URL_ENV_SET=0
if [[ -n "${CONTAINER_REGISTRY+x}" || -n "${REGISTRY+x}" ]]; then
  CONTAINER_REGISTRY_ENV_SET=1
fi
if [[ -n "${CONTAINER_NAMESPACE+x}" || -n "${DOCKERHUB_NAMESPACE+x}" || -n "${DOCKERHUB_USERNAME+x}" ]]; then
  CONTAINER_NAMESPACE_ENV_SET=1
fi
if [[ -n "${IMAGE_TAG+x}" || -n "${TAG+x}" ]]; then
  IMAGE_TAG_ENV_SET=1
fi
if [[ -n "${TAGGER_BASE_URL+x}" ]]; then
  TAGGER_BASE_URL_ENV_SET=1
fi
CONTAINER_REGISTRY="${CONTAINER_REGISTRY:-${REGISTRY:-docker.io}}"
CONTAINER_NAMESPACE="${CONTAINER_NAMESPACE:-${DOCKERHUB_NAMESPACE:-${DOCKERHUB_USERNAME:-}}}"
IMAGE_TAG="${IMAGE_TAG:-${TAG:-latest}}"
SKIP_IMAGE_SYNC="${SKIP_IMAGE_SYNC:-0}"
TAGGER_BASE_URL="${TAGGER_BASE_URL:-http://host.docker.internal:8000}"
CONTAINER_REGISTRY_SET=0
CONTAINER_NAMESPACE_SET=0
IMAGE_TAG_SET=0
TAGGER_BASE_URL_SET=0

usage() {
  cat <<'EOF'
Usage:
  ./init.sh [options]

Options:
  --tagger-base-url <url> Write CHAT_IMAGE_TAGGER_BASE_URL into .env
  --registry <host>       Container registry host (default: docker.io)
  --namespace <namespace> Container registry namespace/org for image sync
  --dockerhub-namespace <namespace>
                          Legacy alias for --namespace
  --tag <tag>             Override image tag (default: latest)
  --skip-image-sync       Skip docker pull + retag
  -h, --help              Show help

Environment variables:
  DATA_ROOT         Runtime data root (default: ./.data)
  ENV_FILE          Target .env file path (default: ./.env)
  ENV_EXAMPLE       Template env file path (default: ./.env.example)
  CONTAINER_REGISTRY
                    Container registry host (default: docker.io)
  CONTAINER_NAMESPACE
                    Registry namespace/org for image sync
  REGISTRY          Alias for CONTAINER_REGISTRY
  DOCKERHUB_NAMESPACE
                    Legacy Docker Hub namespace fallback
  DOCKERHUB_USERNAME
                    Legacy Docker Hub username fallback for namespace
  IMAGE_TAG         Image tag for image sync and compose
  SKIP_IMAGE_SYNC=1 Skip image sync

What it does:
  1. Create Docker/runtime directories under ./.data
  2. Initialize queue/log files if missing
  3. Copy .env.example to .env if .env does not exist
  4. Write CONTAINER_REGISTRY / CONTAINER_NAMESPACE / IMAGE_TAG / optional tagger base URL into .env
  5. Pull registry logger/processor images and retag them locally for compose

Precedence:
  CLI options > environment variables > existing .env values > defaults
EOF
}

err() {
  echo "[init.sh] $*" >&2
  exit 1
}

ensure_dir() {
  local path="$1"
  mkdir -p "$path"
  printf '[init.sh] Ready dir: %s\n' "$path"
}

ensure_file() {
  local path="$1"
  local default_content="$2"

  mkdir -p "$(dirname "$path")"
  if [[ ! -e "$path" ]]; then
    printf '%s' "$default_content" > "$path"
    printf '[init.sh] Created file: %s\n' "$path"
  else
    printf '[init.sh] Keep existing file: %s\n' "$path"
  fi
}

has_env_key() {
  local key="$1"
  local file="$2"
  [[ -f "$file" ]] || return 1
  grep -q "^${key}=" "$file"
}

get_env_value() {
  local key="$1"
  local file="$2"
  [[ -f "$file" ]] || return 1
  awk -v key="$key" '
    index($0, key "=") == 1 {
      print substr($0, length(key) + 2)
      exit
    }
  ' "$file"
}

set_env_value() {
  local key="$1"
  local value="$2"
  local file="$3"
  local tmp_file="${file}.tmp"

  awk -v key="$key" -v value="$value" '
    BEGIN { updated = 0 }
    index($0, key "=") == 1 {
      print key "=" value
      updated = 1
      next
    }
    { print }
    END {
      if (!updated) {
        print key "=" value
      }
    }
  ' "$file" > "$tmp_file"

  mv "$tmp_file" "$file"
  printf '[init.sh] Updated %s in %s\n' "$key" "$file"
}

ensure_env_value() {
  local key="$1"
  local value="$2"
  local file="$3"

  if has_env_key "$key" "$file"; then
    printf '[init.sh] Keep existing %s in %s\n' "$key" "$file"
  else
    set_env_value "$key" "$value" "$file"
  fi
}

sync_image() {
  local remote_image="$1"
  local local_image="$2"

  printf '[init.sh] Pulling image: %s\n' "$remote_image"
  docker pull "$remote_image"

  if [[ "$remote_image" != "$local_image" ]]; then
    printf '[init.sh] Retagging image: %s -> %s\n' "$remote_image" "$local_image"
    docker tag "$remote_image" "$local_image"
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tagger-base-url)
      [[ $# -ge 2 ]] || err "Missing value for --tagger-base-url"
      TAGGER_BASE_URL="$2"
      TAGGER_BASE_URL_SET=1
      shift 2
      ;;
    --registry)
      [[ $# -ge 2 ]] || err "Missing value for $1"
      CONTAINER_REGISTRY="$2"
      CONTAINER_REGISTRY_SET=1
      shift 2
      ;;
    --namespace|--dockerhub-namespace)
      [[ $# -ge 2 ]] || err "Missing value for $1"
      CONTAINER_NAMESPACE="$2"
      CONTAINER_NAMESPACE_SET=1
      shift 2
      ;;
    --tag)
      [[ $# -ge 2 ]] || err "Missing value for --tag"
      IMAGE_TAG="$2"
      IMAGE_TAG_SET=1
      shift 2
      ;;
    --skip-image-sync)
      SKIP_IMAGE_SYNC=1
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

ensure_dir "$DATA_ROOT"
ensure_dir "$DATA_ROOT/nats"
ensure_dir "$DATA_ROOT/postgres"
ensure_dir "$DATA_ROOT/pgadmin"
ensure_dir "$DATA_ROOT/chat"
ensure_dir "$DATA_ROOT/chat/chat_images"
ensure_dir "$DATA_ROOT/chat/chat_images/group"
ensure_dir "$DATA_ROOT/chat/chat_images/private"

ensure_file "$DATA_ROOT/chat/chat_image_tagger_queue.json" '[]'
ensure_file "$DATA_ROOT/chat/group_images.jsonl" ''
ensure_file "$DATA_ROOT/chat/group_image_tags.jsonl" ''

if [[ ! -f "$ENV_FILE" ]]; then
  [[ -f "$ENV_EXAMPLE" ]] || err "Env template not found: $ENV_EXAMPLE"
  cp "$ENV_EXAMPLE" "$ENV_FILE"
  printf '[init.sh] Created env file from template: %s\n' "$ENV_FILE"
else
  printf '[init.sh] Keep existing env file: %s\n' "$ENV_FILE"
fi

if [[ "$CONTAINER_REGISTRY_SET" -eq 0 && "$CONTAINER_REGISTRY_ENV_SET" -eq 0 ]]; then
  EXISTING_REGISTRY="$(get_env_value "CONTAINER_REGISTRY" "$ENV_FILE" || true)"
  if [[ -n "${EXISTING_REGISTRY:-}" ]]; then
    CONTAINER_REGISTRY="$EXISTING_REGISTRY"
  fi
fi

if [[ "$CONTAINER_NAMESPACE_SET" -eq 0 && "$CONTAINER_NAMESPACE_ENV_SET" -eq 0 ]]; then
  EXISTING_NAMESPACE="$(get_env_value "CONTAINER_NAMESPACE" "$ENV_FILE" || true)"
  if [[ -z "${EXISTING_NAMESPACE:-}" ]]; then
    EXISTING_NAMESPACE="$(get_env_value "DOCKERHUB_NAMESPACE" "$ENV_FILE" || true)"
  fi
  if [[ -n "${EXISTING_NAMESPACE:-}" ]]; then
    CONTAINER_NAMESPACE="$EXISTING_NAMESPACE"
  fi
fi

if [[ "$IMAGE_TAG_SET" -eq 0 && "$IMAGE_TAG_ENV_SET" -eq 0 ]]; then
  EXISTING_IMAGE_TAG="$(get_env_value "IMAGE_TAG" "$ENV_FILE" || true)"
  if [[ -n "${EXISTING_IMAGE_TAG:-}" ]]; then
    IMAGE_TAG="$EXISTING_IMAGE_TAG"
  fi
fi

if [[ "$TAGGER_BASE_URL_SET" -eq 0 && "$TAGGER_BASE_URL_ENV_SET" -eq 0 ]]; then
  EXISTING_TAGGER_BASE_URL="$(get_env_value "CHAT_IMAGE_TAGGER_BASE_URL" "$ENV_FILE" || true)"
  if [[ -n "${EXISTING_TAGGER_BASE_URL:-}" ]]; then
    TAGGER_BASE_URL="$EXISTING_TAGGER_BASE_URL"
  fi
fi

CONTAINER_REGISTRY="${CONTAINER_REGISTRY#https://}"
CONTAINER_REGISTRY="${CONTAINER_REGISTRY#http://}"
CONTAINER_REGISTRY="${CONTAINER_REGISTRY%/}"
CONTAINER_NAMESPACE="${CONTAINER_NAMESPACE#/}"
CONTAINER_NAMESPACE="${CONTAINER_NAMESPACE%/}"
TAGGER_BASE_URL="${TAGGER_BASE_URL%/}"

if [[ -z "$CONTAINER_REGISTRY" ]]; then
  err "CONTAINER_REGISTRY must not be empty"
fi

if [[ -z "$CONTAINER_NAMESPACE" ]]; then
  err "CONTAINER_NAMESPACE, DOCKERHUB_NAMESPACE, or DOCKERHUB_USERNAME is required"
fi

if [[ "$CONTAINER_REGISTRY_SET" -eq 1 || "$CONTAINER_REGISTRY_ENV_SET" -eq 1 ]]; then
  set_env_value "CONTAINER_REGISTRY" "$CONTAINER_REGISTRY" "$ENV_FILE"
else
  ensure_env_value "CONTAINER_REGISTRY" "$CONTAINER_REGISTRY" "$ENV_FILE"
fi

if [[ "$CONTAINER_NAMESPACE_SET" -eq 1 || "$CONTAINER_NAMESPACE_ENV_SET" -eq 1 ]]; then
  set_env_value "CONTAINER_NAMESPACE" "$CONTAINER_NAMESPACE" "$ENV_FILE"
else
  ensure_env_value "CONTAINER_NAMESPACE" "$CONTAINER_NAMESPACE" "$ENV_FILE"
fi

if [[ "$IMAGE_TAG_SET" -eq 1 || "$IMAGE_TAG_ENV_SET" -eq 1 ]]; then
  set_env_value "IMAGE_TAG" "$IMAGE_TAG" "$ENV_FILE"
else
  ensure_env_value "IMAGE_TAG" "$IMAGE_TAG" "$ENV_FILE"
fi

if [[ "$TAGGER_BASE_URL_SET" -eq 1 || "$TAGGER_BASE_URL_ENV_SET" -eq 1 ]]; then
  set_env_value "CHAT_IMAGE_TAGGER_BASE_URL" "$TAGGER_BASE_URL" "$ENV_FILE"
else
  ensure_env_value "CHAT_IMAGE_TAGGER_BASE_URL" "$TAGGER_BASE_URL" "$ENV_FILE"
fi

REMOTE_LOGGER_IMAGE="${CONTAINER_REGISTRY}/${CONTAINER_NAMESPACE}/data-assistant-logger:${IMAGE_TAG}"
REMOTE_PROCESSOR_IMAGE="${CONTAINER_REGISTRY}/${CONTAINER_NAMESPACE}/data-assistant-processor:${IMAGE_TAG}"
LOCAL_LOGGER_IMAGE="data-assistant-logger:${IMAGE_TAG}"
LOCAL_PROCESSOR_IMAGE="data-assistant-processor:${IMAGE_TAG}"

if [[ "$SKIP_IMAGE_SYNC" != "1" ]]; then
  command -v docker >/dev/null 2>&1 || err "docker is required for image sync"
  sync_image "$REMOTE_LOGGER_IMAGE" "$LOCAL_LOGGER_IMAGE"
  sync_image "$REMOTE_PROCESSOR_IMAGE" "$LOCAL_PROCESSOR_IMAGE"
else
  printf '[init.sh] Skip image sync.\n'
fi

cat <<EOF
[init.sh] Init complete.

Data root:       $DATA_ROOT
Env file:        $ENV_FILE
Tagger base URL: ${TAGGER_BASE_URL:-<not changed>}
Registry:            $CONTAINER_REGISTRY
Registry namespace:  $CONTAINER_NAMESPACE
Image tag:            $IMAGE_TAG
Remote logger:        $REMOTE_LOGGER_IMAGE
Remote processor:     $REMOTE_PROCESSOR_IMAGE
Local logger:         $LOCAL_LOGGER_IMAGE
Local processor:      $LOCAL_PROCESSOR_IMAGE

Next steps:
  1. Check CHAT_IMAGE_TAGGER_BASE_URL in $ENV_FILE
  2. docker compose up -d
EOF
