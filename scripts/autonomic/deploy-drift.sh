#!/bin/bash
# Autonomic deploy drift watcher — compares the local main branch against
# the remote and optionally a production server's deployed HEAD.
#
# Healthy state: production HEAD == origin HEAD == local HEAD.
# Drift cases:
#   1. Local has commits not yet pushed to origin (local ahead)
#   2. Origin has commits not yet pulled to production (origin ahead of prod)
#   3. Production has commits not in origin (drift on prod — should never happen)
#   4. Local missing commits from origin (local behind)
#
# State files written:
#   echo/autonomic-deploy-drift.json   — latest run only
#   echo/autonomic-deploy-drift.log    — append-only history
#
# DOES NOT touch echo/pulse.json. Same architectural rule as
# smoke-beat.sh: watchers own their own state files.
#
# CONFIGURATION:
#   Set these environment variables or edit the defaults below:
#   - DEPLOY_SSH_CMD: SSH command to reach production (e.g. "ssh user@server")
#   - DEPLOY_APP_PATH: Path to app on production server (e.g. "/opt/myapp")
#   - DEPLOY_REMOTE: Git remote name (default: "origin")
#   - DEPLOY_BRANCH: Git branch name (default: "main")
#
# USAGE (manual):
#   scripts/autonomic/deploy-drift.sh
#
# USAGE (cron — runs every 15 minutes):
#   */15 * * * * cd /path/to/your/project \
#     && ./scripts/autonomic/deploy-drift.sh > /dev/null 2>&1

set -u

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_DIR"

# Configuration — override via environment variables
REMOTE="${DEPLOY_REMOTE:-origin}"
BRANCH="${DEPLOY_BRANCH:-main}"
SSH_CMD="${DEPLOY_SSH_CMD:-}"
APP_PATH="${DEPLOY_APP_PATH:-}"

STATUS_FILE="echo/autonomic-deploy-drift.json"
LOG_FILE="echo/autonomic-deploy-drift.log"
TIMESTAMP_UTC=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
TIMESTAMP_LOCAL=$(date '+%Y-%m-%d %H:%M:%S')

# 1. Local HEAD
git fetch "$REMOTE" "$BRANCH" --quiet 2>/dev/null || true
LOCAL_HEAD=$(git rev-parse "$BRANCH" 2>/dev/null || echo "unknown")
LOCAL_SHORT=${LOCAL_HEAD:0:8}

# 2. Origin HEAD (post-fetch)
ORIGIN_HEAD=$(git rev-parse "$REMOTE/$BRANCH" 2>/dev/null || echo "unknown")
ORIGIN_SHORT=${ORIGIN_HEAD:0:8}

# 3. Production HEAD via SSH (only if configured and reachable)
DROPLET_HEAD="not-configured"
if [ -n "$SSH_CMD" ] && [ -n "$APP_PATH" ]; then
    DROPLET_HEAD=$($SSH_CMD "cd $APP_PATH && git rev-parse HEAD" 2>/dev/null || echo "unreachable")
fi
DROPLET_SHORT=${DROPLET_HEAD:0:8}

# Compute drift state
DRIFT_REASONS="[]"
OK="True"

if [ "$DROPLET_HEAD" = "unreachable" ]; then
    DRIFT_REASONS='["production server unreachable"]'
    OK="False"
elif [ "$LOCAL_HEAD" = "unknown" ] || [ "$ORIGIN_HEAD" = "unknown" ]; then
    DRIFT_REASONS='["local git rev-parse failed"]'
    OK="False"
else
    REASONS=()
    if [ "$LOCAL_HEAD" != "$ORIGIN_HEAD" ]; then
        AHEAD=$(git rev-list --count "$REMOTE/$BRANCH..$BRANCH" 2>/dev/null || echo "?")
        BEHIND=$(git rev-list --count "$BRANCH..$REMOTE/$BRANCH" 2>/dev/null || echo "?")
        if [ "$AHEAD" != "0" ] && [ "$AHEAD" != "?" ]; then
            REASONS+=("\"local ahead of origin by $AHEAD commit(s) — push pending\"")
        fi
        if [ "$BEHIND" != "0" ] && [ "$BEHIND" != "?" ]; then
            REASONS+=("\"local behind origin by $BEHIND commit(s) — pull pending\"")
        fi
    fi
    if [ "$DROPLET_HEAD" != "not-configured" ] && [ "$DROPLET_HEAD" != "$ORIGIN_HEAD" ]; then
        REASONS+=("\"production at $DROPLET_SHORT, origin at $ORIGIN_SHORT �� production not yet pulled\"")
    fi
    if [ ${#REASONS[@]} -gt 0 ]; then
        OK="False"
        DRIFT_REASONS="[$(IFS=,; echo "${REASONS[*]}")]"
    fi
fi

# Write the current-state JSON file
python3 <<PYEOF
import json
data = {
    "checked_at": "$TIMESTAMP_UTC",
    "local_head": "$LOCAL_HEAD",
    "origin_head": "$ORIGIN_HEAD",
    "production_head": "$DROPLET_HEAD",
    "ok": $OK,
    "drift_reasons": $DRIFT_REASONS,
}
with open("$STATUS_FILE", "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
PYEOF

# Append rolling log line
if [ "$OK" = "True" ]; then
    echo "[$TIMESTAMP_LOCAL] OK   local=$LOCAL_SHORT origin=$ORIGIN_SHORT production=$DROPLET_SHORT" >> "$LOG_FILE"
else
    REASON_FLAT=$(echo "$DRIFT_REASONS" | tr -d '[]"' | tr ',' ';')
    echo "[$TIMESTAMP_LOCAL] DRIFT local=$LOCAL_SHORT origin=$ORIGIN_SHORT production=$DROPLET_SHORT — $REASON_FLAT" >> "$LOG_FILE"
fi

# Print summary for cron-log capture
echo "[$TIMESTAMP_LOCAL] deploy drift: ok=$OK local=$LOCAL_SHORT origin=$ORIGIN_SHORT production=$DROPLET_SHORT"

[ "$OK" = "True" ] && exit 0 || exit 1
