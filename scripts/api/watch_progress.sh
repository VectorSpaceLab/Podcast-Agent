#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

usage() {
  cat <<'EOF'
Usage:
  scripts/api/watch_progress.sh [options]

Examples:
  scripts/api/watch_progress.sh \
    --url "https://www.youtube.com/watch?v=xxxx" \
    --question "这个视频主要讲了什么？"

  scripts/api/watch_progress.sh --task-id "<task-id>"

Options:
  --base-url   API base URL. Defaults to http://127.0.0.1:8080.
  --url        Source URL. Required unless --task-id is provided.
  --question   Question to answer. Required unless --task-id is provided.
  --task-id    Watch an existing task instead of creating a new one.
  --interval   Poll interval in seconds. Defaults to 2.
  --max-polls  Maximum number of progress polls. Defaults to 600.
  -h, --help   Show this help.
EOF
}

BASE_URL="http://127.0.0.1:8080"
URL=""
QUESTION=""
TASK_ID=""
INTERVAL="2"
MAX_POLLS="600"

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
    --task-id)
      TASK_ID="${2:-}"
      shift 2
      ;;
    --interval)
      INTERVAL="${2:-}"
      shift 2
      ;;
    --max-polls)
      MAX_POLLS="${2:-}"
      shift 2
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

if [[ -z "$BASE_URL" ]]; then
  echo "--base-url must not be empty." >&2
  exit 2
fi

if [[ -z "$TASK_ID" && ( -z "$URL" || -z "$QUESTION" ) ]]; then
  echo "--url and --question must not be empty unless --task-id is provided." >&2
  exit 2
fi

if [[ ! "$MAX_POLLS" =~ ^[0-9]+$ || "$MAX_POLLS" -lt 1 ]]; then
  echo "--max-polls must be a positive integer." >&2
  exit 2
fi

if [[ ! "$INTERVAL" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
  echo "--interval must be a positive number." >&2
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
REQUEST_FILE="$(mktemp)"
RESPONSE_FILE="$(mktemp)"
PROGRESS_FILE="$(mktemp)"
trap 'rm -f "$REQUEST_FILE" "$RESPONSE_FILE" "$PROGRESS_FILE"' EXIT

if [[ -z "$TASK_ID" ]]; then
  PODCAST_AGENT_ASK_URL="$URL" PODCAST_AGENT_ASK_QUESTION="$QUESTION" ".venv/bin/python" - <<'PY' >"$REQUEST_FILE"
import json
import os

print(json.dumps({"url": os.environ["PODCAST_AGENT_ASK_URL"], "question": os.environ["PODCAST_AGENT_ASK_QUESTION"]}, ensure_ascii=False))
PY

  curl -sS -X POST "$BASE_URL/videochat/api/tasks" \
    -H "Content-Type: application/json" \
    --data-binary "@$REQUEST_FILE" \
    -o "$RESPONSE_FILE"

  TASK_ID="$(".venv/bin/python" - "$RESPONSE_FILE" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    payload = json.load(handle)

if "task_id" not in payload:
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
    raise SystemExit(1)
print(payload["task_id"])
PY
)"
  echo "created task_id=$TASK_ID"
else
  echo "watching task_id=$TASK_ID"
fi

AFTER_SEQ="0"

for ((poll=1; poll<=MAX_POLLS; poll++)); do
  curl -sS "$BASE_URL/videochat/api/tasks/$TASK_ID/progress?after_seq=$AFTER_SEQ&limit=100" \
    -o "$PROGRESS_FILE"

  READ_RESULT="$(".venv/bin/python" - "$PROGRESS_FILE" "$AFTER_SEQ" <<'PY'
import json
import sys


def format_duration(ms):
    try:
        total_seconds = max(0, int(ms) // 1000)
    except (TypeError, ValueError):
        return "n/a"
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def format_range(min_ms, max_ms):
    if min_ms is None or max_ms is None:
        return "n/a"
    return f"{format_duration(min_ms)}-{format_duration(max_ms)}"


with open(sys.argv[1], "r", encoding="utf-8") as handle:
    payload = json.load(handle)

if "error" in payload:
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
    raise SystemExit(2)

for event in payload.get("events", []):
    seq = event.get("seq", "")
    phase = event.get("phase", "")
    message = event.get("message", "")
    print(f"[{seq}] {phase} - {message}", file=sys.stderr)

timing = payload.get("timing") if isinstance(payload.get("timing"), dict) else {}
task_timing = timing.get("task") if isinstance(timing.get("task"), dict) else {}
phase_timing = timing.get("phase") if isinstance(timing.get("phase"), dict) else {}

if task_timing:
    print(
        f"timing task elapsed={format_duration(task_timing.get('elapsed_ms'))} "
        f"remaining={format_range(task_timing.get('remaining_min_ms'), task_timing.get('remaining_max_ms'))} "
        f"confidence={task_timing.get('confidence', 'n/a')}",
        file=sys.stderr,
    )

if phase_timing:
    phase = phase_timing.get("phase", "n/a")
    progress = phase_timing.get("progress") if isinstance(phase_timing.get("progress"), dict) else {}
    progress_suffix = ""
    if progress:
        progress_suffix = f" progress={progress.get('completed', '?')}/{progress.get('total', '?')}"
    print(
        f"timing phase={phase} elapsed={format_duration(phase_timing.get('elapsed_ms'))} "
        f"remaining={format_range(phase_timing.get('remaining_min_ms'), phase_timing.get('remaining_max_ms'))} "
        f"confidence={phase_timing.get('confidence', 'n/a')}{progress_suffix}",
        file=sys.stderr,
    )

print(json.dumps({"after_seq": payload.get("next_after_seq", sys.argv[2]), "status": payload.get("status", "")}, ensure_ascii=False))
PY
)"

  AFTER_SEQ="$(".venv/bin/python" - "$READ_RESULT" <<'PY'
import json
import sys
print(json.loads(sys.argv[1])["after_seq"])
PY
)"
  STATUS="$(".venv/bin/python" - "$READ_RESULT" <<'PY'
import json
import sys
print(json.loads(sys.argv[1])["status"])
PY
)"

  if [[ "$STATUS" == "completed" ]]; then
    echo "completed task_id=$TASK_ID"
    echo "fetch report:"
    echo "curl \"$BASE_URL/videochat/api/tasks/$TASK_ID/report\""
    exit 0
  fi

  if [[ "$STATUS" == "failed" ]]; then
    echo "failed task_id=$TASK_ID" >&2
    exit 1
  fi

  sleep "$INTERVAL"
done

echo "timed out waiting for task_id=$TASK_ID" >&2
exit 124

