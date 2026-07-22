#!/usr/bin/env bash
# Safely inspect and start the repository's CircleMUD service.

set -euo pipefail

readonly TOOL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly REPO_ROOT="$(git -C "$TOOL_DIR" rev-parse --show-toplevel)"
readonly COMPOSE_FILE="$REPO_ROOT/week0_explore/infrastructure/docker-compose.yml"
readonly SERVICE="circlemud"
readonly MUD_HOST="${MUD_HOST:-localhost}"
readonly MUD_PORT="${MUD_PORT:-4000}"
readonly START_TIMEOUT="${MUD_SERVER_START_TIMEOUT:-60}"

die() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

require_network_tool() {
  command -v nc >/dev/null || die "nc is required"
}

require_docker() {
  command -v docker >/dev/null || die "Docker is required to start CircleMUD; enable Docker Desktop WSL integration or start the MUD outside this agent"
  [[ -f "$COMPOSE_FILE" ]] || die "missing Compose file: $COMPOSE_FILE"
  docker compose version >/dev/null 2>&1 || die "Docker Compose is unavailable"
  docker info >/dev/null 2>&1 || die "Docker daemon is unavailable or permission was denied"
}

compose() {
  docker compose -f "$COMPOSE_FILE" "$@"
}

service_running() {
  compose ps --status running --services 2>/dev/null | grep -Fxq "$SERVICE"
}

port_ready() {
  nc -z -w 1 "$MUD_HOST" "$MUD_PORT" >/dev/null 2>&1
}

status() {
  local service_state="unknown (Docker unavailable)" port_state="closed"
  port_ready && port_state="ready"
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    service_state="stopped"
    service_running && service_state="running"
  fi
  printf 'CircleMUD service: %s\n' "$service_state"
  printf 'MUD endpoint %s:%s: %s\n' "$MUD_HOST" "$MUD_PORT" "$port_state"
  [[ "$port_state" == "ready" ]]
}

ensure() {
  local deadline
  if port_ready; then
    printf 'CircleMUD endpoint is already ready at %s:%s; Docker is not needed.\n' "$MUD_HOST" "$MUD_PORT"
    return 0
  fi
  require_docker
  if ! service_running && port_ready; then
    die "port $MUD_PORT is occupied outside the CircleMUD Compose service"
  fi
  service_running || compose up --build -d "$SERVICE"
  deadline=$((SECONDS + START_TIMEOUT))
  until port_ready; do
    ((SECONDS < deadline)) || { compose logs --tail 80 "$SERVICE" >&2 || true; die "MUD did not become ready"; }
    service_running || { compose logs --tail 80 "$SERVICE" >&2 || true; die "CircleMUD exited during startup"; }
    sleep 2
  done
  printf 'CircleMUD is running at %s:%s.\n' "$MUD_HOST" "$MUD_PORT"
}

require_network_tool
case "${1:-}" in
  status) status ;;
  ensure) ensure ;;
  logs) compose logs --tail "${MUD_LOG_LINES:-100}" "$SERVICE" ;;
  *) die "usage: mud-server.sh <status|ensure|logs>" ;;
esac
