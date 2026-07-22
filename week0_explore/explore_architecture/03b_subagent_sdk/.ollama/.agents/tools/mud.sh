#!/usr/bin/env bash
# One-command interface for low-capability agents operating CircleMUD.

set -euo pipefail

readonly TOOL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly LOGIN_TOOL="$TOOL_DIR/mud-login.sh"
readonly SERVER_TOOL="$TOOL_DIR/mud-server.sh"

die() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

usage() {
  cat <<'USAGE'
Usage: .ollama/.agents/tools/mud.sh <action> [command]

  doctor          Check required programs, files, and credential variables.
  start           Ensure CircleMUD is ready and create/reuse one logged-in session.
  status          Show server readiness and authenticated-session state.
  capture         Show recent redacted output from the existing session.
  send 'command'  Send exactly one command through the authenticated session.
  logs            Show recent bounded CircleMUD server logs.
  stop            Close only the managed client session; keep the server running.

Start with: mud.sh doctor && mud.sh start
Then use:  mud.sh send 'look'
USAGE
}

doctor() {
  local failed=0
  local command_name
  for command_name in git python3 tmux nc; do
    if command -v "$command_name" >/dev/null 2>&1; then
      printf 'OK command: %s\n' "$command_name"
    else
      printf 'MISSING command: %s\n' "$command_name" >&2
      failed=1
    fi
  done

  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    printf 'OK optional command: docker compose\n'
  elif nc -z -w 1 "${MUD_HOST:-localhost}" "${MUD_PORT:-4000}" >/dev/null 2>&1; then
    printf 'OK endpoint: MUD is ready; Docker is not required.\n'
  else
    printf 'MISSING startup path: Docker Compose is unavailable and the MUD port is closed.\n' >&2
    failed=1
  fi

  [[ -x "$LOGIN_TOOL" ]] || { printf 'MISSING executable: %s\n' "$LOGIN_TOOL" >&2; failed=1; }
  [[ -x "$SERVER_TOOL" ]] || { printf 'MISSING executable: %s\n' "$SERVER_TOOL" >&2; failed=1; }

  "$LOGIN_TOOL" check-env || failed=1
  ((failed == 0)) || die "doctor found missing requirements"
  printf 'MUD tools are ready.\n'
}

send_command() {
  [[ $# -eq 1 ]] || die "send requires exactly one quoted MUD command"
  [[ -n "$1" ]] || die "refusing to send an empty MUD command"
  [[ "$1" != *$'\n'* && "$1" != *$'\r'* ]] || die "send accepts only one line"
  printf '%s\n' "$1" | "$LOGIN_TOOL" send
}

case "${1:-help}" in
  doctor) doctor ;;
  start)
    "$SERVER_TOOL" ensure
    "$LOGIN_TOOL" start
    ;;
  status)
    "$SERVER_TOOL" status || true
    "$LOGIN_TOOL" status || true
    ;;
  capture) "$LOGIN_TOOL" capture ;;
  send)
    shift
    send_command "$@"
    ;;
  logs) "$SERVER_TOOL" logs ;;
  stop) "$LOGIN_TOOL" stop ;;
  help|-h|--help) usage ;;
  *) usage >&2; exit 2 ;;
esac
