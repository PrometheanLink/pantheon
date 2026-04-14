# Pygmalion — Headless Browser Eyes for AI Agents

Pygmalion gives Claude Code (or any AI coding agent) the ability to **see what the user sees** by driving a real Chrome browser against your deployed site.

## Why You Need This

When a user reports "the page is broken":
- `curl` tells you the HTTP status (200 OK — not helpful)
- Server logs show no errors
- You start guessing: cache? minification? auth state?

**Pygmalion tells you exactly what broke.** It captures:
- Every `console.log`, `console.warn`, `console.error` with source file + line number
- Every uncaught JavaScript exception with **full Chrome stack traces** (not minified)
- Every failed network request
- A full-page screenshot

One Pygmalion probe replaces 4 dead-end commits worth of guessing.

## Setup

### Prerequisites

```bash
# Install Playwright
npm install playwright

# Install Chromium (headless)
npx playwright install chromium
```

That's it. No Docker, no Selenium, no browser drivers to manage.

### Your First Probe

```bash
# 1. Get a JWT token from your app's auth system
#    (however you mint tokens — API call, CLI tool, etc.)
TOKEN="your-jwt-token-here"

# 2. Probe a page
PANTHEON_TOKEN=$TOKEN \
  PANTHEON_URL=https://yoursite.com/dashboard \
  node scripts/pygmalion/probe.mjs
```

### Output

```
==> probe target: https://yoursite.com/dashboard
==> viewport: 1400 x 900
==> mode: navigate-only

==> initial nav: 200
==> took: 2616 ms
==> final url: https://yoursite.com/dashboard
==> title: My App — Dashboard
==> screenshot: /tmp/pygmalion/probe-2026-04-14T01-28-37-834Z.png

=== CONSOLE LOG (3 entries) ===
[log] @https://yoursite.com/_next/static/chunks/app.js:42:15 App mounted
[warn] @https://yoursite.com/_next/static/chunks/page.js:128:8 Deprecation warning: ...
[error] @https://yoursite.com/_next/static/chunks/page.js:256:12 Failed to fetch user data

=== PAGE ERRORS (1) ===
TypeError: Cannot read properties of undefined (reading 'name')
    at UserProfile (https://yoursite.com/_next/static/chunks/page.js:312:18)
    at renderWithHooks (https://yoursite.com/_next/static/chunks/framework.js:1234:22)
    ...
---

=== NETWORK FAILURES (0) ===
  (none)
```

Exit code is `0` if no page errors, `1` if errors found. Use this in CI or smoke tests.

## Click-Through Testing

Probe a page, then click a link and check the destination:

```bash
PANTHEON_TOKEN=$TOKEN \
  PANTHEON_URL=https://yoursite.com/dashboard \
  PANTHEON_CLICK_SELECTOR='a[href*="/dashboard/jobs/"]:first-of-type' \
  node scripts/pygmalion/probe.mjs
```

This navigates to `/dashboard`, clicks the first job link, and captures errors on both pages.

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PANTHEON_TOKEN` | Yes | — | JWT auth token |
| `PANTHEON_URL` | Yes | — | URL to probe |
| `PANTHEON_CLICK_SELECTOR` | No | — | CSS selector to click after nav |
| `PANTHEON_OUTPUT_DIR` | No | `/tmp/pygmalion` | Screenshot output dir |
| `PANTHEON_VIEWPORT` | No | `1400x900` | Browser viewport size |
| `PANTHEON_WAIT_MS` | No | `2000` | Extra wait after nav (ms) |
| `PANTHEON_TIMEOUT_MS` | No | `30000` | Navigation timeout (ms) |

## How Auth Works

Pygmalion injects the JWT into `localStorage` via `page.addInitScript()` **before** any user JavaScript runs. This means:

1. Chrome launches clean (no cookies, no cache)
2. The init script sets `localStorage.access_token = YOUR_TOKEN`
3. Your app's JavaScript reads the token from localStorage on mount
4. The page loads as an authenticated user

If your app uses a different storage key (e.g., `token`, `authToken`, `session`), edit the `addInitScript` call in `probe.mjs`.

## Token Minting

You need a way to generate valid JWTs for testing. Options:

### Option A: CLI tool (if your backend has one)
```bash
TOKEN=$(python3 -c "from app.utils.auth import create_access_token; print(create_access_token(...))")
```

### Option B: API login
```bash
TOKEN=$(curl -s -X POST https://yoursite.com/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"..."}' | jq -r '.access_token')
```

### Option C: Direct DB token generation (for testing only)
```bash
# From inside your backend container
docker exec your_backend python3 -c "
from app.utils.auth import create_access_token
from datetime import timedelta
token = create_access_token(
    data={'sub': 'USER_UUID', 'role': 'admin'},
    expires_delta=timedelta(hours=8)
)
print(token)
"
```

## When to Use Pygmalion

**ALWAYS use Pygmalion when:**
- User reports a UI bug you can't see from server logs
- A page "works for you" but not for the user
- You're debugging minified JavaScript errors
- After a deploy, before announcing "it's live"
- End-to-end smoke testing

**Don't use Pygmalion for:**
- API-only bugs (use curl/httpie instead)
- Database issues
- Backend crashes (check docker logs)

## The 6x Multiplier

In real-world testing, Pygmalion resolved a frontend TDZ (Temporal Dead Zone) bug in **5 tool calls** that took **4 dead-end commits** without it. The Chrome stack trace pointed directly to the line, while minified error messages were useless.

**Rule: If you see a UI bug, your first instinct should be to probe. Don't guess.**

## Integration with Smoke Tests

You can wrap Pygmalion in an autonomic smoke test that runs on a cron:

```bash
#!/bin/bash
# scripts/autonomic/ui-smoke.sh
TOKEN=$(./scripts/pygmalion/mint-token.sh)
PAGES=(
  "https://yoursite.com/dashboard"
  "https://yoursite.com/dashboard/jobs/kanban"
  "https://yoursite.com/dashboard/equipment"
)
FAIL=0
for url in "${PAGES[@]}"; do
  PANTHEON_TOKEN=$TOKEN PANTHEON_URL=$url node scripts/pygmalion/probe.mjs > /dev/null 2>&1
  if [ $? -ne 0 ]; then
    echo "FAIL: $url"
    FAIL=$((FAIL + 1))
  fi
done
echo "UI smoke: $((${#PAGES[@]} - FAIL))/${#PAGES[@]} passed"
exit $FAIL
```

Add to cron for continuous UI monitoring:
```bash
0 */4 * * * cd /path/to/project && ./scripts/autonomic/ui-smoke.sh >> echo/autonomic-ui-smoke.log 2>&1
```
