#!/usr/bin/env bash
# mud-server.sh - Check and safely start the repository's CircleMUD service.

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)"
readonly COMPOSE_FILE="$REPO_ROOT/week0_explore/infrastructure/docker-compose.yml"
readonly SERVICE="circlemud"
readonly MUD_HOST="${MUD_HOST:-localhost}"
readonly MUD_PORT="${MUD_PORT:-4000}"
readonly START_TIMEOUT="${MUD_SERVER_START_TIMEOUT:-60}"

die() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

require_prerequisites() {
  command -v docker >/dev/null || die "docker is required"
  command -v nc >/dev/null || die "nc is required for the port readiness check"
  [[ -f "$COMPOSE_FILE" ]] || die "missing Compose file: $COMPOSE_FILE"
  docker compose version >/dev/null 2>&1 || die "Docker Compose is unavailable"
  docker info >/dev/null 2>&1 || die "the Docker daemon is unavailable or permission was denied"
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

show_status() {
  local service_state="stopped"
  local port_state="closed"
  service_running && service_state="running"
  port_ready && port_state="ready"
  printf 'Compose service %s: %s\n' "$SERVICE" "$service_state"
  printf 'MUD endpoint %s:%s: %s\n' "$MUD_HOST" "$MUD_PORT" "$port_state"
  [[ "$service_state" == "running" && "$port_state" == "ready" ]]
}

wait_until_ready() {
  local deadline=$((SECONDS + START_TIMEOUT))
  until port_ready; do
    if ((SECONDS >= deadline)); then
      compose logs --tail 80 "$SERVICE" >&2 || true
      die "MUD port did not become ready within ${START_TIMEOUT}s"
    fi
    if ! service_running; then
      compose logs --tail 80 "$SERVICE" >&2 || true
      die "Compose service exited before the MUD port became ready"
    fi
    sleep 2
  done
}

ensure_running() {
  if service_running && port_ready; then
    printf 'MUD server is already running and ready.\n'
    return 0
  fi

  if ! service_running && port_ready; then
    die "port $MUD_PORT is already in use by a process outside this Compose service"
  fi

  if service_running; then
    printf 'MUD service is running; waiting for port %s.\n' "$MUD_PORT"
  else
    printf 'Starting MUD service with Docker Compose.\n'
    compose up --build -d "$SERVICE"
  fi

  wait_until_ready
  printf 'MUD server is running and ready at %s:%s.\n' "$MUD_HOST" "$MUD_PORT"
}

usage() {
  cat <<'USAGE'
Usage: data/code/mud-server.sh <status|ensure|logs>

  status  Report Compose and port readiness without changing state.
  ensure  Start circlemud only when necessary, then wait for port 4000.
  logs    Show the most recent CircleMUD container logs.

This tool intentionally does not expose Docker down, volume deletion, pruning,
or cleanup operations because those can destroy persistent game state.
USAGE
}

main() {
  case "${1:-}" in
    -h|--help|help) usage; return 0 ;;
  esac

  require_prerequisites
  case "${1:-}" in
    status) show_status ;;
    ensure) ensure_running ;;
    logs) compose logs --tail "${MUD_LOG_LINES:-100}" "$SERVICE" ;;
    *) usage >&2; return 2 ;;
  esac
}

main "$@"
