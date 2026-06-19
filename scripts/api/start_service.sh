#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

usage() {
  cat <<'EOF'
Usage:
  scripts/api/start_service.sh [options]

Examples:
  scripts/api/start_service.sh
  scripts/api/start_service.sh --background
  scripts/api/start_service.sh --report-mode pdf --background

Options:
  --host         Host to bind. Defaults to 127.0.0.1.
  --port         Port to bind. Defaults to 8080.
  --task-root    Runtime task directory. Defaults to output/api.
  --report-mode  Report output mode: markdown, html, pdf, xhs, all. Defaults to markdown.
  --log-file     Background log path. Defaults to output/api/server.log.
  --background   Start with nohup and print the process id.
  -h, --help     Show this help.
EOF
}

HOST="127.0.0.1"
PORT="8080"
TASK_ROOT="output/api"
REPORT_MODE="markdown"
LOG_FILE=""
BACKGROUND="0"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      HOST="${2:-}"
      shift 2
      ;;
    --port)
      PORT="${2:-}"
      shift 2
      ;;
    --task-root)
      TASK_ROOT="${2:-}"
      shift 2
      ;;
    --report-mode)
      REPORT_MODE="${2:-}"
      shift 2
      ;;
    --log-file)
      LOG_FILE="${2:-}"
      shift 2
      ;;
    --background)
      BACKGROUND="1"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$HOST" || -z "$PORT" || -z "$TASK_ROOT" || -z "$REPORT_MODE" ]]; then
  echo "--host, --port, --task-root, and --report-mode must not be empty." >&2
  exit 2
fi

if [[ ! "$PORT" =~ ^[0-9]+$ ]]; then
  echo "--port must be an integer." >&2
  exit 2
fi

case "$REPORT_MODE" in
  markdown|html|pdf|xhs|all) ;;
  *)
    echo "--report-mode must be one of: markdown, html, pdf, xhs, all." >&2
    exit 2
    ;;
esac

if [[ ! -x ".venv/bin/python" ]]; then
  echo "Missing .venv/bin/python. Create the venv and install dependencies first." >&2
  exit 1
fi

mkdir -p "$TASK_ROOT"

ARGS=(
  "-m" "podcast_agent.api.server"
  "--host" "$HOST"
  "--port" "$PORT"
  "--task-root" "$TASK_ROOT"
  "--report-mode" "$REPORT_MODE"
)

if [[ "$BACKGROUND" == "1" ]]; then
  if [[ -z "$LOG_FILE" ]]; then
    LOG_FILE="$TASK_ROOT/server.log"
  fi
  mkdir -p "$(dirname "$LOG_FILE")"
  nohup ".venv/bin/python" "${ARGS[@]}" >"$LOG_FILE" 2>&1 &
  PID="$!"
  echo "Podcast-Agent API starting at http://$HOST:$PORT"
  echo "pid=$PID"
  echo "log=$LOG_FILE"
  echo "report_mode=$REPORT_MODE"
  exit 0
fi

exec ".venv/bin/python" "${ARGS[@]}"

