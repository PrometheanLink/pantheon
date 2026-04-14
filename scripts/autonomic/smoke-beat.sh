#!/bin/bash
# Autonomic smoke beat — runs an endpoint smoke test and records the
# result to echo/autonomic-status.json + echo/autonomic-smoke.log.
#
# Pattern: an external scheduler (cron) runs this script periodically.
# It exercises the production API surface and records pass/fail to a
# dedicated state file. If something breaks while no human is watching,
# the next session sees it on startup.
#
# IMPORTANT: This script does NOT call `echo/echo beat` because echo's
# pulse.json is singleton — beating it under a different session name
# would overwrite the active dev session's pulse. Autonomic monitoring
# uses its own state files.
#
# State files written:
#   echo/autonomic-status.json   — latest run only (timestamp, pass, fail, failures)
#   echo/autonomic-smoke.log     — append-only history of every run
#
# USAGE (manual):
#   scripts/autonomic/smoke-beat.sh
#
# USAGE (cron — runs hourly at :07):
#   7 * * * * cd /path/to/your/project && \
#     ./scripts/autonomic/smoke-beat.sh > /dev/null 2>&1
#
# PREREQUISITES:
#   You must create a smoke-test-endpoints.sh script that:
#   - Tests your API endpoints (curl-based)
#   - Prints "  Passed: N" and "  Failed: N" lines
#   - Exits 0 on all pass, 1 on any failure
#   - Prints "Failures:" section with "  - endpoint: reason" lines on failure

set -u

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_DIR"

STATUS_FILE="echo/autonomic-status.json"
LOG_FILE="echo/autonomic-smoke.log"
SMOKE_SCRIPT="scripts/autonomic/smoke-test-endpoints.sh"

# Check that the smoke test script exists
if [ ! -x "$SMOKE_SCRIPT" ]; then
    echo "ERROR: Smoke test script not found or not executable: $SMOKE_SCRIPT"
    echo "Create it first. See the comments in this file for the expected interface."
    exit 2
fi

SMOKE_OUTPUT=$(mktemp)
trap 'rm -f "$SMOKE_OUTPUT"' EXIT

"$SMOKE_SCRIPT" > "$SMOKE_OUTPUT" 2>&1
EXIT_CODE=$?

# Strip ANSI color codes before parsing
strip_ansi() { sed 's/\x1b\[[0-9;]*m//g'; }
PASS=$(strip_ansi < "$SMOKE_OUTPUT" | grep -E "^  Passed:" | grep -oE '[0-9]+' | head -1)
FAIL=$(strip_ansi < "$SMOKE_OUTPUT" | grep -E "^  Failed:" | grep -oE '[0-9]+' | head -1)
PASS="${PASS:-0}"
FAIL="${FAIL:-0}"

TIMESTAMP=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
TIMESTAMP_LOCAL=$(date '+%Y-%m-%d %H:%M:%S')

# Capture failure list as a JSON-safe string
FAILURES_JSON="[]"
if [ "$EXIT_CODE" -ne 0 ]; then
    FAILURES_JSON=$(strip_ansi < "$SMOKE_OUTPUT" \
        | awk '/^Failures:/{flag=1; next} flag && /^[[:space:]]*-/' \
        | sed 's/^[[:space:]]*-[[:space:]]*//' \
        | python3 -c "import sys, json; print(json.dumps([l.strip() for l in sys.stdin if l.strip()]))")
fi

# Write the current-state JSON file
OK_STR=$([ "$EXIT_CODE" -eq 0 ] && echo "True" || echo "False")
python3 <<PYEOF
import json
data = {
    "checked_at": "$TIMESTAMP",
    "pass": int("$PASS"),
    "fail": int("$FAIL"),
    "ok": $OK_STR,
    "failures": $FAILURES_JSON,
}
with open("$STATUS_FILE", "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
PYEOF

# Append a one-line summary to the rolling log
if [ "$EXIT_CODE" -eq 0 ]; then
    echo "[$TIMESTAMP_LOCAL] OK   pass=$PASS" >> "$LOG_FILE"
else
    echo "[$TIMESTAMP_LOCAL] FAIL pass=$PASS fail=$FAIL" >> "$LOG_FILE"
    strip_ansi < "$SMOKE_OUTPUT" | sed 's/^/    /' >> "$LOG_FILE"
fi

# Print to stdout for cron-log capture
echo "[$TIMESTAMP_LOCAL] autonomic smoke: pass=$PASS fail=$FAIL exit=$EXIT_CODE"

exit "$EXIT_CODE"
