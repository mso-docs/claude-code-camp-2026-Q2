#!/usr/bin/env bash
# mud-login.sh - Manage an authenticated persistent MUD session for coding agents.

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly DRIVER="$SCRIPT_DIR/mud-session.py"
readonly SESSION_NAME="${MUD_TMUX_SESSION:-opencode-mud}"
readonly LOGIN_TIMEOUT="${MUD_LOGIN_TIMEOUT:-40}"

die() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

load_project_env() {
  local repo_root
  repo_root="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null)" ||
    die "could not locate the Git worktree"

  if [[ -f "$repo_root/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "$repo_root/.env"
    set +a
  fi
}

require_prerequisites() {
  command -v git >/dev/null || die "git is required"
  command -v python3 >/dev/null || die "python3 is required"
  command -v tmux >/dev/null || die "tmux is required"
  [[ -f "$DRIVER" ]] || die "missing session driver: $DRIVER"
}

session_exists() {
  tmux has-session -t "$SESSION_NAME" 2>/dev/null
}

capture_raw() {
  tmux capture-pane -p -S -200 -t "$SESSION_NAME"
}

capture_redacted() {
  local output
  output="$(capture_raw)"
  if [[ -n "${MUD_USERNAME:-}" ]]; then
    output="${output//"$MUD_USERNAME"/[username]}"
  fi
  if [[ -n "${MUD_PASSWORD:-}" ]]; then
    output="${output//"$MUD_PASSWORD"/[password]}"
  fi
  printf '%s\n' "$output"
}

wait_for_login() {
  local deadline=$((SECONDS + LOGIN_TIMEOUT))
  local output

  while ((SECONDS < deadline)); do
    session_exists || die "MUD session exited during login"
    output="$(capture_raw)"
    if [[ "$output" == *"MUD_LOGIN_OK"* ]]; then
      capture_redacted
      return 0
    fi
    if [[ "$output" == *"MUD_LOGIN_ERROR:"* ]]; then
      capture_redacted
      return 1
    fi
    sleep 1
  done

  capture_redacted
  die "login did not finish within ${LOGIN_TIMEOUT}s"
}

start_session() {
  [[ -n "${MUD_USERNAME:-}" ]] || die "set MUD_USERNAME in the repository-root .env"
  [[ -n "${MUD_PASSWORD:-}" ]] || die "set MUD_PASSWORD in the repository-root .env"

  if session_exists; then
    printf 'Reusing tmux session %s.\n' "$SESSION_NAME"
    capture_redacted
    return 0
  fi

  tmux new-session -d -s "$SESSION_NAME" \
    "python3 '$DRIVER'; driver_status=\$?; printf '\nMUD_DRIVER_EXIT=%s\n' \"\$driver_status\"; sleep 30"
  wait_for_login
}

send_command() {
  local command
  session_exists || die "no session named $SESSION_NAME; run $0 start first"
  IFS= read -r command || die "send expects one command on stdin"
  [[ -n "$command" ]] || die "refusing to send an empty gameplay command"

  tmux send-keys -l -t "$SESSION_NAME" -- "$command"
  tmux send-keys -t "$SESSION_NAME" Enter
  sleep "${MUD_COMMAND_WAIT:-2}"
  capture_redacted
}

stop_session() {
  if ! session_exists; then
    printf 'No tmux session named %s is running.\n' "$SESSION_NAME"
    return 0
  fi

  tmux send-keys -l -t "$SESSION_NAME" -- "__close__"
  tmux send-keys -t "$SESSION_NAME" Enter
  sleep 1
  if session_exists; then
    tmux kill-session -t "$SESSION_NAME"
  fi
  printf 'Stopped tmux session %s.\n' "$SESSION_NAME"
}

usage() {
  cat <<'USAGE'
Usage: data/code/mud-login.sh <start|status|capture|send|stop>

  start    Open one persistent connection and complete the prompt-driven login.
  status   Report whether the persistent session is running.
  capture  Print recent session output with credentials redacted.
  send     Read one gameplay command from stdin, send it, and capture output.
  stop     Close only the managed persistent session.

Credentials must be set as MUD_USERNAME and MUD_PASSWORD in the repository-root
.env or inherited environment. Never pass credentials as command arguments.
USAGE
}

main() {
  require_prerequisites
  load_project_env

  case "${1:-}" in
    start) start_session ;;
    status)
      if session_exists; then
        printf 'MUD session %s is running.\n' "$SESSION_NAME"
      else
        printf 'MUD session %s is not running.\n' "$SESSION_NAME"
        return 1
      fi
      ;;
    capture)
      session_exists || die "no session named $SESSION_NAME"
      capture_redacted
      ;;
    send) send_command ;;
    stop) stop_session ;;
    -h|--help|help) usage ;;
    *) usage >&2; return 2 ;;
  esac
}

main "$@"
