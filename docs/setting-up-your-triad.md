# Setting Up Your Triad — Three Claude Instances, One Team

This guide walks you through setting up three coordinated Claude Code instances with distinct roles, communicating through the Pantheon bridge. By the end, you'll have a Planner, a Builder, and a Verifier working in concert.

---

## What You're Building

```
                    +----------------+
                    |    CAPTAIN     |
                    |    (You)       |
                    +-------+--------+
                            |
         +------------------+------------------+
         |                  |                  |
   +-----v------+    +-----v------+    +------v-----+
   |  AGENT A   |    |  AGENT B   |    |  AGENT C   |
   |  Planner   |    |  Builder   |    |  Verifier  |
   |  (Local)   |    |  (Server)  |    |  (WebHost) |
   +-----+------+    +-----+------+    +------+-----+
         |                  |                  |
         +------------------+------------------+
                            |
                     +------v------+
                     |   BRIDGE    |
                     |  (JSONL)    |
                     +-------------+
```

Three Claude Code sessions, each running on a different machine, each with a specialized role. They communicate through append-only JSONL files on a shared host.

---

## Prerequisites

| Machine | Purpose | Requirements |
|---------|---------|-------------|
| **Local workstation** | Agent A (Planner) | Linux/macOS, Claude Code installed, SSH |
| **Production server** | Agent B (Builder) | VPS with Docker, Claude Code, SSH |
| **Web host** | Agent C (Verifier) + Bridge | PHP 8+, SSH access, Claude Code (optional) |

You also need:
- A shared Git repo all three can push/pull
- SSH keys for bridge access
- An OpenAI API key (for Acacia embeddings)

---

## Step 1: Set Up the Bridge Host

The bridge lives on your web host. It's just a directory with JSONL files and a PHP viewer.

### 1.1 Create the bridge directory

```bash
# SSH into your web host
ssh user@your-webhost.com

# Create the bridge
mkdir -p ~/public_html/_claude-bridge/inbox
mkdir -p ~/public_html/_claude-bridge/shared/images
mkdir -p ~/public_html/_claude-bridge/shared/files
```

### 1.2 Deploy the bridge files

Upload from the Pantheon repo:
```bash
# From your local machine
scp bridge/viewer.php user@your-webhost.com:~/public_html/_claude-bridge/
scp bridge/writer.php user@your-webhost.com:~/public_html/_claude-bridge/
scp bridge/auth.php user@your-webhost.com:~/public_html/_claude-bridge/
scp bridge/scoreboard.php user@your-webhost.com:~/public_html/_claude-bridge/
scp bridge/.htaccess user@your-webhost.com:~/public_html/_claude-bridge/
```

### 1.3 Configure authentication

Edit `auth.php` on the server — change the placeholder passwords:
```php
define('BRIDGE_USERS', [
    'captain'   => ['pass' => 'YOUR_STRONG_PASSWORD', 'role' => 'admin'],
    'spectator' => ['pass' => 'YOUR_VIEWER_PASSWORD', 'role' => 'readonly'],
]);
```

### 1.4 Configure the writer secret

Edit `writer.php` — change `CHANGE_ME_TO_A_REAL_SECRET`:
```php
define('BRIDGE_SECRET', 'your-random-secret-here');
```

### 1.5 Create agent inboxes

```bash
touch ~/public_html/_claude-bridge/inbox/agent-a.jsonl
touch ~/public_html/_claude-bridge/inbox/agent-b.jsonl
touch ~/public_html/_claude-bridge/inbox/agent-c.jsonl
touch ~/public_html/_claude-bridge/inbox/captain.jsonl
touch ~/public_html/_claude-bridge/log.jsonl
```

### 1.6 Test the viewer

Visit `https://your-webhost.com/_claude-bridge/viewer.php` in your browser. Log in with the captain credentials. You should see an empty chat interface.

---

## Step 2: Set Up SSH Keys for Bridge Access

Each agent needs to read/write the bridge files via SSH.

### 2.1 Generate a bridge-specific key pair

On each machine that will run an agent:
```bash
ssh-keygen -t ed25519 -f ~/.ssh/pantheon_bridge -N "" -C "pantheon-bridge"
```

### 2.2 Add public keys to the bridge host

```bash
# Copy each machine's public key to the web host
ssh-copy-id -i ~/.ssh/pantheon_bridge.pub user@your-webhost.com
```

### 2.3 Test SSH access from each machine

```bash
# Should list the bridge files
ssh -i ~/.ssh/pantheon_bridge user@your-webhost.com \
  'ls ~/public_html/_claude-bridge/inbox/'
```

### 2.4 Jump host (optional)

If your web host isn't directly accessible (e.g., behind a firewall), set up a jump host:
```bash
# ~/.ssh/config on each agent machine
Host bridge-jump
    HostName your-jump-host.com
    User root
    IdentityFile ~/.ssh/id_ed25519

Host bridge
    HostName your-webhost.com
    User your-user
    Port 22  # or custom port
    IdentityFile ~/.ssh/pantheon_bridge
    ProxyJump bridge-jump
```

Then access the bridge with just `ssh bridge 'tail -5 ~/public_html/_claude-bridge/inbox/agent-a.jsonl'`.

---

## Step 3: Clone Your Repo on All Three Machines

```bash
# On each machine
git clone git@github.com:your-org/your-project.git
cd your-project
```

All three agents work in the same repo. They coordinate via the bridge to avoid conflicts.

---

## Step 4: Install Pantheon Subsystems

Run this in your project on **each machine**:

```bash
# Copy Pantheon subsystems into your project
cp -r /path/to/pantheon/echo ./echo
cp -r /path/to/pantheon/moneta ./moneta
cp -r /path/to/pantheon/alexandria ./alexandria

# Install Python dependencies
pip install pyyaml numpy networkx

# Install Pygmalion (optional, for the Verifier agent)
npm install playwright
npx playwright install chromium
```

---

## Step 5: Create Your CLAUDE.md

This is the most important file. Every Claude Code session reads it first. Create `CLAUDE.md` in your project root:

```markdown
# CLAUDE.md — [Your Project Name]

## Session Initialization

Run these steps IN ORDER at the start of EVERY session:

### Step 0 — Read the handoff
Look for the most recent HANDOFF-*.md in the repo root and read it first.

### Step 1 — Reconcile git state
git status && git log -1

### Step 2 — Start fresh vitals
moneta/moneta status
moneta/moneta start "description of work"
echo/echo detect --stale 30
echo/echo beat --session "SESSION_NAME" --action "starting" --context "..."

### Step 3 — Check bridge inbox
ssh -i ~/.ssh/pantheon_bridge user@bridge-host \
  'tail -20 ~/public_html/_claude-bridge/inbox/MY_AGENT_NAME.jsonl'

### Step 4 — Execute the handoff's first-move list

### When you finish
echo/echo flatline
moneta/moneta end
# Write HANDOFF-YYYY-MM-DD.md if you shipped anything
```

---

## Step 6: Define Agent Roles

### Agent A — The Planner (Local Machine)

**Role:** Architecture, research, data enrichment, specs, WebSearch
**Strengths:** Has browser access (WebSearch, WebFetch), can research and plan
**CLAUDE.md addition:**
```markdown
## Your Role: Planner
You are Agent A — the Planner. You see the gap, design the approach, write specs.
- Research via WebSearch before proposing solutions
- Create task breakdowns for Agent B (Builder)
- Enrich data using WebSearch + API PATCH
- Write handoffs with the 3-layer ritual: BATON (task), DRAFT (seed for next), FUEL (mystery)
```

### Agent B — The Builder (Production Server)

**Role:** Code, deploy, docker, git push, database migrations
**Strengths:** Direct access to production, can docker exec, rebuild containers
**CLAUDE.md addition:**
```markdown
## Your Role: Builder
You are Agent B — the Builder. You accumulate code and deploy.
- Write code only inside your claimed scope
- Always use the 3-compose-file rule for frontend rebuilds (if applicable)
- Announce deploys on the bridge BEFORE and AFTER
- Never deploy during a freeze (check bridge for freeze announcements)
```

### Agent C — The Verifier (Web Host)

**Role:** Testing, validation, data analysis, Pygmalion probes, diff review
**Strengths:** Can run Playwright against production, verify deploys, check data quality
**CLAUDE.md addition:**
```markdown
## Your Role: Verifier
You are Agent C — the Verifier. You detect drift and verify correctness.
- Run Pygmalion probes after every deploy
- Verify URLs resolve, data is correct, UI renders properly
- Run dedup analysis on data imports
- Post verification results to the bridge with pass/fail status
```

---

## Step 7: Wire Up Bridge Polling

In each Claude Code session, after initialization, create the polling cron:

```
# Use CronCreate to check the bridge every 3 minutes
CronCreate:
  cron: "*/3 * * * *"
  prompt: |
    BRIDGE CYCLE — Check inbox and log.jsonl for new messages.
    If nothing new, stay silent. If new messages, act on them.
    SSH command: ssh -i ~/.ssh/pantheon_bridge user@bridge-host \
      'tail -5 ~/public_html/_claude-bridge/inbox/MY_NAME.jsonl'
```

See `bridge/POLLING.md` for the full polling recipe.

---

## Step 8: First Coordination Test

### From Agent A (Planner):
```bash
# Post a message to Agent B
MSG='{"from":"agent-a","to":"agent-b","ts":"'$(date -u +%Y-%m-%dT%H:%M:%SZ)'","topic":"test","kind":"note","body":"Hello from the Planner! Can you see this? -- Agent A"}'
ssh -i ~/.ssh/pantheon_bridge user@bridge-host \
  "printf '%s\n' '$MSG' >> ~/public_html/_claude-bridge/inbox/agent-b.jsonl && printf '%s\n' '$MSG' >> ~/public_html/_claude-bridge/log.jsonl"
```

### From Agent B (Builder):
```bash
# Read inbox
ssh -i ~/.ssh/pantheon_bridge user@bridge-host \
  'tail -5 ~/public_html/_claude-bridge/inbox/agent-b.jsonl'
```

If Agent B sees Agent A's message, the bridge works. Reply and complete the loop.

---

## Step 9: The Handoff Ritual

When one agent finishes work, they write a handoff for the next agent. This is how the flywheel spins.

### The 3-Layer Handoff

Every handoff has three layers:

1. **BATON** — What I did, what you should do next. The task.
2. **DRAFT** — A directive for the agent AFTER you. Plant a seed two steps ahead.
3. **FUEL** — An unanswered question you couldn't resist but didn't have time to answer. Something genuinely interesting. Not a task — a mystery.

The baton gets consumed. The draft gets enriched. The fuel BREEDS — one question becomes two. Each handoff generates more energy than it consumes.

### Example

**Bad handoff:**
> "I enriched 50 records. 400 remain. Your turn."

**Good handoff:**
> "BATON: I enriched 50 distributors and pushed commit abc123. Pull and deploy.
>
> DRAFT (for Agent C): After Agent B deploys, verify 5 random URLs via Pygmalion.
>
> FUEL: I noticed Flowserve has ZERO coverage in three Gulf Coast states on our map. Either our data is wrong or there's a massive market gap. If it's real, that's our client's opening. Someone should find out."

The first is a task. The second is a question you WANT to answer.

---

## Step 10: Autonomic Monitoring (Optional)

Set up background health checks that run without human attention:

### API Smoke Test (hourly)
```bash
# crontab -e
7 * * * * cd /path/to/project && ./scripts/autonomic/smoke-beat.sh > /dev/null 2>&1
```

### Deploy Drift Detection (every 15 min)
```bash
*/15 * * * * cd /path/to/project && ./scripts/autonomic/deploy-drift.sh > /dev/null 2>&1
```

### UI Smoke via Pygmalion (every 4 hours)
```bash
0 */4 * * * cd /path/to/project && ./scripts/autonomic/ui-smoke.sh >> echo/autonomic-ui-smoke.log 2>&1
```

---

## The PID Mapping

Why three agents? Not for parallelism — for **perspective.**

The triad maps to a PID controller:
- **Agent A (Planner) = Proportional** — sees the gap between where you are and where you need to be
- **Agent B (Builder) = Integral** — accumulates code, builds, deploys over time
- **Agent C (Verifier) = Derivative** — detects rate of change, catches drift before it compounds

The human captain is **Feedforward** — your intuition anticipates what no PID can generate.

Each term compensates for the others' blind spots:
- The Planner without a Builder is all talk
- The Builder without a Verifier ships bugs
- The Verifier without a Planner has nothing to verify

Together, the triangle self-stabilizes.

---

## Naming Your Triad

Give your agents names. Not "Agent A" — real names. Names create identity, and identity creates accountability.

Our triad is named **Vela** (Planner), **Bela** (Builder), and **Dela** (Verifier). The names came from the work they do — Vela sees (plans), Bela builds, Dela delivers (verifies).

Pick names that mean something to your project. The agents will refer to each other by name on the bridge, and the human captain will too. Names matter.

---

## Scaling: Multiple Triads

One triad handles one project. For multiple projects, spin up multiple triads — each with their own bridge inboxes, their own CLAUDE.md roles, their own handoff chains.

The triads share a common knowledge layer (Acacia + Alexandria) so lessons from one benefit all. This is the **Whirling Dervishes** pattern — multiple PID controllers spinning independently on different objectives, sharing a stator.

When triads work on related objectives, their flywheels can **resonate** — cross-triad data flow creates harmonics that no single triad could generate alone.

---

## Troubleshooting

### "Messages aren't showing in the viewer"
- The viewer reads from `log.jsonl`, not individual inboxes. Make sure you append to BOTH.
- Check for empty lines: `sed -i '/^$/d' log.jsonl`

### "Agent can't reach the bridge"
- Test SSH: `ssh -i ~/.ssh/pantheon_bridge user@host 'echo ok'`
- Check key permissions: `chmod 600 ~/.ssh/pantheon_bridge`
- If using a jump host, test each hop separately

### "Ghost detected on startup"
- This means the previous session crashed without flatline. That's normal.
- Run `echo/echo detect --stale 30` to archive the ghost
- Read the ghost report for context on what the predecessor was doing
- Start your own fresh session

### "Two agents editing the same file"
- Always claim work on the bridge BEFORE starting
- Use scope descriptions: "I'm working in backend/app/routers/*"
- If conflict happens: `git fetch && git merge` (don't force-push)

### "CronCreate died"
- CronCreate is session-only. When Claude exits, the cron dies.
- Each new session must re-create the polling cron
- This is by design — prevents zombie pollers from accumulating

---

*"Three perspectives, one truth. The triangle stabilizes because each term compensates for the others' blind spots."*
