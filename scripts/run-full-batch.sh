#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CASES_PATH="${CASES_PATH:-"$ROOT_DIR/examples/full-report-cases.json"}"
OUTPUT_ROOT="${OUTPUT_ROOT:-"$ROOT_DIR/output"}"
MAX_JOBS="${MAX_JOBS:-3}"

if command -v podcast-agent >/dev/null 2>&1; then
  PODCAST_AGENT="podcast-agent"
elif [[ -x "$ROOT_DIR/.venv/bin/podcast-agent" ]]; then
  PODCAST_AGENT="$ROOT_DIR/.venv/bin/podcast-agent"
else
  echo "podcast-agent command not found. Install the project first, for example: pip install -e ."
  exit 1
fi

if [[ ! -f "$CASES_PATH" ]]; then
  echo "Cases file not found: $CASES_PATH"
  exit 1
fi

echo "Using command: $PODCAST_AGENT"
echo "Cases: $CASES_PATH"
echo "Output root: $OUTPUT_ROOT"
echo "Max jobs: $MAX_JOBS"
echo

"$PODCAST_AGENT" full-batch \
  --cases "$CASES_PATH" \
  --output-root "$OUTPUT_ROOT" \
  --max-jobs "$MAX_JOBS" \
  "$@"
