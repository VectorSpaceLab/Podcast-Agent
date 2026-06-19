#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

usage() {
  cat <<'EOF'
Usage:
  scripts/api/ask_followup.sh --question <question> [options]

Examples:
  scripts/api/ask_followup.sh --task-id "<task-id>" --question "视频中有哪些关键观点？"
  scripts/api/ask_followup.sh --question "视频中有哪些关键观点？"

Options:
  --base-url   API base URL. Defaults to http://127.0.0.1:8080.
  --task-root  Runtime task directory. Defaults to output/api.
  --task-id    Task ID. Defaults to the most recent task in task-root.
  --question   Followup question.
  --raw        Print raw JSON instead of a compact summary plus pretty JSON.
  -h, --help   Show this help.
EOF
}

BASE_URL="http://127.0.0.1:8080"
TASK_ROOT="output/api"
TASK_ID=""
QUESTION=""
RAW="0"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base-url)
      BASE_URL="${2:-}"
      shift 2
      ;;
    --task-root)
      TASK_ROOT="${2:-}"
      shift 2
      ;;
    --task-id)
      TASK_ID="${2:-}"
      shift 2
      ;;
    --question)
      QUESTION="${2:-}"
      shift 2
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

if [[ -z "$BASE_URL" || -z "$TASK_ROOT" || -z "$QUESTION" ]]; then
  echo "--base-url, --task-root, and --question must not be empty." >&2
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

if [[ -z "$TASK_ID" ]]; then
  TASK_DIR="$(ls -dt "$TASK_ROOT"/*/ 2>/dev/null | head -1 || true)"
  if [[ -z "$TASK_DIR" ]]; then
    echo "No task directories found in $TASK_ROOT." >&2
    exit 1
  fi
  TASK_ID="$(basename "$TASK_DIR")"
fi

TASK_DIR="$TASK_ROOT/$TASK_ID"
if [[ ! -d "$TASK_DIR" ]]; then
  echo "Task directory not found: $TASK_DIR" >&2
  exit 1
fi

if ! find "$TASK_DIR" \( -name "*.vtt" -o -name "*.srt" \) -print -quit | grep -q .; then
  echo "No subtitle file found in task directory: $TASK_DIR" >&2
  exit 1
fi

BASE_URL="${BASE_URL%/}"
REQUEST_FILE="$(mktemp)"
RESPONSE_FILE="$(mktemp)"
trap 'rm -f "$REQUEST_FILE" "$RESPONSE_FILE"' EXIT

PODCAST_AGENT_FOLLOWUP_QUESTION="$QUESTION" ".venv/bin/python" - <<'PY' >"$REQUEST_FILE"
import json
import os

print(json.dumps({"question": os.environ["PODCAST_AGENT_FOLLOWUP_QUESTION"]}, ensure_ascii=False))
PY

HTTP_CODE="$(curl -sS -w "%{http_code}" -X POST "$BASE_URL/videochat/api/tasks/$TASK_ID/followup" \
  -H "Content-Type: application/json" \
  --data-binary "@$REQUEST_FILE" \
  -o "$RESPONSE_FILE")"

if [[ "$RAW" == "1" ]]; then
  cat "$RESPONSE_FILE"
  printf '\n'
  [[ "$HTTP_CODE" == "200" ]]
  exit $?
fi

echo "task_id=$TASK_ID"
echo "http_status=$HTTP_CODE"
".venv/bin/python" - "$RESPONSE_FILE" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    payload = json.load(handle)

if "error" in payload:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    raise SystemExit(1)

segments = payload.get("segments", [])
print(f"sufficient={payload.get('sufficient')}")
print(f"reason={payload.get('reason') or ''}")
print(f"segments={len(segments)}")
for index, segment in enumerate(segments[:3], start=1):
    text = str(segment.get("text") or "")
    print(f"{index}. [{segment.get('start')} --> {segment.get('end')}] {text[:80]}")
print()
print(json.dumps(payload, ensure_ascii=False, indent=2))
PY

