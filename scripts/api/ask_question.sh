#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

usage() {
  cat <<'EOF'
Usage:
  scripts/api/ask_question.sh --url <source-url> --question <question> [options]

Examples:
  scripts/api/ask_question.sh \
    --url "https://www.bilibili.com/video/BV122E96LEuS" \
    --question "这个视频主要讲了什么？"

  scripts/api/ask_question.sh \
    --url "https://www.bilibili.com/video/BV122E96LEuS" \
    --question "这个视频主要讲了什么？" \
    --async

Options:
  --base-url   API base URL. Defaults to http://127.0.0.1:8080.
  --url        Source URL.
  --question   Question to answer from the source.
  --sync       Use /videochat/api/tasks/sync. This is the default.
  --async      Use /videochat/api/tasks and return a task id immediately.
  --raw        Print raw JSON instead of pretty JSON.
  -h, --help   Show this help.
EOF
}

BASE_URL="http://127.0.0.1:8080"
URL=""
QUESTION=""
MODE="sync"
RAW="0"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base-url)
      BASE_URL="${2:-}"
      shift 2
      ;;
    --url)
      URL="${2:-}"
      shift 2
      ;;
    --question)
      QUESTION="${2:-}"
      shift 2
      ;;
    --sync)
      MODE="sync"
      shift
      ;;
    --async)
      MODE="async"
      shift
      ;;
    --raw)
      RAW="1"
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

if [[ -z "$BASE_URL" || -z "$URL" || -z "$QUESTION" ]]; then
  echo "--base-url, --url, and --question must not be empty." >&2
  usage >&2
  exit 2
fi

if [[ ! -x ".venv/bin/python" ]]; then
  echo "Missing .venv/bin/python. Create the venv and install dependencies first." >&2
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "Missing curl." >&2
  exit 1
fi

BASE_URL="${BASE_URL%/}"
if [[ "$MODE" == "sync" ]]; then
  ENDPOINT="$BASE_URL/videochat/api/tasks/sync"
else
  ENDPOINT="$BASE_URL/videochat/api/tasks"
fi

REQUEST_FILE="$(mktemp)"
RESPONSE_FILE="$(mktemp)"
trap 'rm -f "$REQUEST_FILE" "$RESPONSE_FILE"' EXIT

PODCAST_AGENT_ASK_URL="$URL" PODCAST_AGENT_ASK_QUESTION="$QUESTION" ".venv/bin/python" - <<'PY' >"$REQUEST_FILE"
import json
import os

print(
    json.dumps(
        {
            "url": os.environ["PODCAST_AGENT_ASK_URL"],
            "question": os.environ["PODCAST_AGENT_ASK_QUESTION"],
        },
        ensure_ascii=False,
    )
)
PY

curl -sS -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  --data-binary "@$REQUEST_FILE" \
  -o "$RESPONSE_FILE"

if [[ "$RAW" == "1" ]]; then
  cat "$RESPONSE_FILE"
  printf '\n'
else
  ".venv/bin/python" -m json.tool "$RESPONSE_FILE"
fi

