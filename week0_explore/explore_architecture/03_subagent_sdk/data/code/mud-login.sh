#!/usr/bin/env bash
# Compatibility entry point. The canonical tool lives beside play-mud.md.

set -euo pipefail

readonly PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
exec "$PROJECT_DIR/.ollama/.agents/tools/mud-login.sh" "$@"
