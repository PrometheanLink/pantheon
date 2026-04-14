<p align="center">
  <img src="pantheon-hero.jpg" alt="Three luminous figures stand in a classical temple around a glowing acacia tree — the Pantheon" width="100%"/>
</p>

<p align="center">
  <h1 align="center">Pantheon</h1>
  <p align="center"><strong>The AI Development Operating System</strong></p>
  <p align="center">Persistent memory, crash recovery, and multi-instance coordination for Claude Code.</p>
</p>

<p align="center">
  <em>A dedication to Gottfried Wilhelm Leibniz, who in 1692 was wise enough<br/>
  to understand what was really going on in civilization and said it<br/>
  in <strong>De la tolérance des religions</strong> — some 334 years ago.<br/>
  And we're still arguing about a puzzle solved ages ago.</em>
</p>

---

## What Is Pantheon?

Pantheon is a scaffolding that transforms Claude Code from a single-session tool into a **persistent, crash-resilient, multi-instance development team.**

Out of the box, Claude Code has no memory between sessions, no crash recovery, no way to coordinate multiple instances, and no way to know if the last session finished its work. Pantheon fixes all of that.

**What you get:**

- **Memory that survives crashes.** Semantic search over your project's accumulated knowledge — lessons, decisions, governance docs, git history. Ask a question, get the answer from 6 months ago.
- **Crash recovery.** Heartbeat monitoring detects when a session dies without finishing. The next session knows exactly what was in progress, what files are at risk, and what to do first.
- **Multi-instance coordination.** Run two or three Claude instances on different machines, each with a specialized role, communicating through an append-only message bridge.
- **Structural intelligence.** A knowledge graph that maps your codebase — which files define which functions, which endpoints call which handlers, which models map to which tables. Query it in natural language.
- **Autonomous health monitoring.** Background watchers that smoke-test your API, detect deployment drift, and alert you when something breaks while nobody's watching.
- **A development protocol.** Session initialization, handoff documents, ghost detection, and a governance framework that keeps AI sessions productive across weeks and months.

---

## The Architecture

```
                        +--------------+
                        |   CAPTAIN    |
                        |   (Human)    |
                        +------+-------+
                               |
        +----------------------+----------------------+
        |                      |                      |
   +----v-----+         +-----v----+         +------v-----+
   | INSTANCE |         | INSTANCE |         | INSTANCE   |
   |    A     |         |    B     |         |    C       |
   | Planner  |         | Builder  |         | Verifier   |
   +----+-----+         +-----+----+         +------+-----+
        |                      |                      |
        +----------+-----------+----------------------+
                   |
            +------v------+
            |   BRIDGE    |   Append-only JSONL
            +------+------+
                   |
      +------------+------------+
      |            |            |
 +----v----+ +----v----+ +----v-----+
 | ACACIA  | |ALEXANDRIA| |  ECHO /  |
 |(Search) | | (Graph)  | | MONETA   |
 +---------+ +---------+ +----------+
```

---

## The Five Systems

### 1. Acacia — The Knowledge Tree

Semantic search over your project's documentation, lessons, and git history. Uses OpenAI embeddings stored in SQLite — no external vector database needed.

```bash
# Ask a question about your project
pantheon acacia ask "how does deployment work"

# Index new content
pantheon acacia ingest --all

# Generate session context
pantheon acacia context "implement payment feature"
```

**How it works:** Chunks your markdown docs and code by headings, generates embeddings via OpenAI `text-embedding-3-small`, stores them as BLOBs in SQLite, and retrieves via numpy cosine similarity. Change detection (content hashing) makes re-indexing cheap.

**What it indexes:**
- `knowledge/governance/` — Operating procedures and standards
- `knowledge/lessons/` — Documented learnings from past incidents
- `knowledge/systems/` — Architecture docs
- `knowledge/roadmap/` — Future work specs
- `CLAUDE.md` — Session initialization protocol
- Git history (last 500 commits)

### 2. Alexandria — The Knowledge Graph

Maps the structural relationships in your codebase using NetworkX. Where Acacia answers "what do we know about X?", Alexandria answers "what is connected to X?"

```python
from pantheon.alexandria import AlexandriaGraph
from pantheon.alexandria.query import ask, format_results

g = AlexandriaGraph("knowledge.json")
results = ask("what handles user authentication", g)
print(format_results(results))
```

**Node types:** files, functions, classes, endpoints, models, instances, builds, lessons, decisions, sessions, clues (breadcrumbs for next incarnation).

**Smart query features:**
- Stemming (`publishing` → `publish`)
- Synonym expansion (`auth` → `[login, oauth, session, jwt]`)
- Type weighting (decisions rank higher than files)
- Edge following (show connected nodes)

### 3. Echo — The Heartbeat

Tracks whether anyone is home. If a session crashes without a graceful shutdown, Echo detects the "ghost" and tells the next session what happened.

```bash
# Record a heartbeat
pantheon echo beat --session "my-session" --action "building feature X" --scan

# Check if the last session is still alive
pantheon echo status

# Detect ghosts from crashed sessions
pantheon echo detect --stale 30

# Gracefully end your session
pantheon echo flatline
```

**Ghost detection works by cross-referencing:**
1. Echo's pulse is stale (no heartbeat in 30+ minutes)
2. Moneta's session is still marked "Active" with an empty body
3. Therefore: the session crashed without finishing

### 4. Moneta — The Session Memory

Records the narrative of each development session: what happened, what decisions were made, what files were touched, what questions remain open.

```bash
# Start a session
pantheon moneta start "building payment integration"

# End a session
pantheon moneta end

# Check status
pantheon moneta status
```

**7-day cycle:** Sessions accumulate for a week, then get summarized, key learnings promote to Acacia lessons, and session files are purged for a fresh start.

### 5. Bridge — The Communication Layer

An append-only JSONL message bus for multi-instance coordination. Each instance has its own inbox. Messages are never edited or deleted — the log IS the memory.

```json
{
  "from": "instance-a",
  "to": "all",
  "ts": "2026-04-13T16:05:00Z",
  "topic": "deployment",
  "kind": "status",
  "body": "Frontend rebuilt and deployed. Smoke test passed."
}
```

**Protocol rules:**
1. Append-only — never edit messages
2. Sign every message (`-- Instance Name`)
3. Check your inbox at session start
4. Claim work before starting (prevents merge conflicts)
5. Announce deploys

### Key Holders — Compaction-Proof Recovery

When an AI instance hits a context compaction, it loses its working memory mid-task. A **key holder** is a persistent file (one per instance) that survives compaction and tells the instance everything it needs to recover:

```markdown
# Key Holder — Instance A (Planner)

## Who Am I?
Name: Instance A | Role: Planner | Machine: local workstation

## Bridge Access
Read inbox:  ssh user@bridge 'tail -20 inbox/planner.jsonl'
Write:       echo '<msg>' | ssh user@bridge 'cat >> inbox/builder.jsonl'

## Credentials
Token: <mint command here> | Expires: <date>

## Current Task (UPDATE EACH SESSION)
Last updated: 2026-04-14
Working on: <what you were doing>

## Recovery Steps
1. Read this file  2. Read bridge inbox  3. Read latest HANDOFF  4. Resume
```

**Where to store key holders:**
- Each instance stores its key holder in a predictable location (e.g., `_pantheon-bridge/keyholder-<role>.md`)
- The key holder is NOT in the conversation context — it's on disk, so it survives compaction
- Every instance must update "Current Task" before any long-running operation
- After a compaction: read key holder → read inbox → read handoff → resume

---

## The Protocol

Every Pantheon session follows this initialization sequence:

```bash
# Step 0 — Read the handoff from the last session
ls -1t HANDOFF-*.md | head -1  # then read it

# Step 1 — Reconcile git state
git status && git log -1
# Crashes can leave staged-but-uncommitted code. Don't start new work until reconciled.

# Step 2 — Start fresh vitals
pantheon moneta status              # Check for stale sessions
pantheon moneta start "description" # Start yours
pantheon echo detect --stale 30     # Find ghosts
pantheon echo beat --session "name" --action "starting" --context "..."

# Step 3 — Check autonomic health
cat echo/autonomic-status.json      # API smoke test results
tail -5 echo/autonomic-smoke.log    # Recent history

# Step 4 — If you just compacted, read your key holder first
cat _pantheon-bridge/keyholder-$(whoami).md  # Recover identity + task

# Step 5 — Check bridge inbox (if multi-instance)
# Read your JSONL inbox for new messages

# Step 6 — Execute the handoff's first-move list
```

When you finish:
```bash
pantheon echo flatline
pantheon moneta end
# Write HANDOFF-YYYY-MM-DD.md if you shipped anything non-trivial
```

---

## Multi-Instance Roles

Pantheon supports up to N instances, but the proven pattern is three + a human captain:

| Role | Responsibility | Best Deployed On |
|------|---------------|-----------------|
| **Captain** (Human) | Direction, decisions, circuit breaker | Everywhere |
| **Planner** | Architecture, research, data enrichment, specs | Local machine |
| **Builder** | Code, deploy, docker, git push | Production server |
| **Verifier** | Testing, validation, data analysis | Separate host |

**Why three?** Not for parallelism (they often work serially). For **perspective.** The planner thinks differently from the builder, who thinks differently from the verifier. Leibniz would approve.

---

## Quick Start

### Single Instance (15 minutes)

```bash
# Clone
git clone https://github.com/PrometheanLink/pantheon.git
cd pantheon

# Install
pip install -e .

# Initialize in your project
cd /path/to/your/project
pantheon init

# This creates:
#   .pantheon/         — Acacia config + database
#   echo/              — Heartbeat system
#   moneta/            — Session tracking
#   knowledge/         — Governance, lessons, roadmap templates
#   CLAUDE.md          — Session init protocol (customize this!)

# Index your project
pantheon acacia ingest --all

# Start your first session
pantheon moneta start "getting started with Pantheon"
pantheon echo beat --session "first-session" --action "initializing" --scan

# Ask questions about your project
pantheon acacia ask "how does authentication work"

# When done
pantheon echo flatline
pantheon moneta end
```

### Multi-Instance (1 hour)

```bash
# On your bridge host (any server with SSH)
mkdir -p _pantheon-bridge/inbox
touch _pantheon-bridge/inbox/{planner,builder,verifier,captain}.jsonl

# Set up SSH keys for each instance
ssh-keygen -t ed25519 -f ~/.ssh/pantheon_bridge -N ""
# Copy public key to bridge host

# On each instance machine, clone the same repo
git clone your-repo.git
cd your-repo
pantheon init

# Test bridge communication
echo '{"from":"planner","to":"all","ts":"'$(date -u +%Y-%m-%dT%H:%M:%SZ)'","kind":"note","body":"Hello from the Planner!"}' | \
  ssh user@bridge-host 'cat >> _pantheon-bridge/inbox/builder.jsonl'

# Read from another instance
ssh user@bridge-host 'tail -5 _pantheon-bridge/inbox/planner.jsonl'
```

---

## Autonomic Layer

Background watchers that run via cron without human attention:

### API Smoke Test (Hourly)
```bash
# Hits every endpoint, records pass/fail to echo/autonomic-status.json
7 * * * * cd /path/to/project && ./scripts/autonomic/smoke-beat.sh
```

### Deploy Drift Detection (Every 15 min)
```bash
# Compares local, origin, and production git HEADs
*/15 * * * * cd /path/to/project && ./scripts/autonomic/deploy-drift.sh
```

### Browser Probe (On-Demand)
```bash
# Headless Chrome: captures JS errors, network failures, screenshots
PANTHEON_TOKEN=$TOKEN PANTHEON_URL=https://yoursite.com/page \
  node scripts/autonomic/pygmalion-probe.mjs
```

---

## Philosophy

### Why "Pantheon"?

A pantheon is a temple that houses all the gods under one roof. Different powers, different domains, one coordinated system. That's what this is — different AI instances with different roles, sharing one knowledge base, one bridge, one protocol.

### The Leibniz Dedication

In 1692, Gottfried Wilhelm Leibniz wrote *De la tolérance des religions*, arguing that the apparent conflicts between different faiths were really just different perspectives on the same underlying truth. The disagreements were about language and vantage point, not substance.

Three hundred and thirty-four years later, we run three AI instances on three different machines. They have different contexts, different capabilities, different roles. They could conflict — pushing incompatible code, duplicating work, contradicting each other. Instead, they coordinate through an append-only bridge, share knowledge through Acacia and Alexandria, and recover from crashes through Echo and Moneta.

Different perspectives. Same truth. The puzzle was solved ages ago.

### Design Principles

1. **Design for crashes, not prevention.** Sessions will die. OOM kills happen. Context windows fill. Build systems that recover gracefully, not systems that try to never fail.

2. **Append-only is a feature.** The temptation to edit messages or clean up old state is strong. Resist it. The log IS the memory. History should be immutable.

3. **Knowledge flows upward.** Ephemeral observations promote to session notes, promote to lessons, promote to core wisdom. Each layer is more durable and more refined than the last.

4. **The human is the circuit breaker.** AI instances present options. Humans decide. When instances disagree, the captain calls it.

5. **Query before you code.** The answer usually already exists somewhere. Acacia search before writing a single line.

6. **Three perspectives > one.** Not for speed. For wisdom. The planner thinks about structure. The builder thinks about implementation. The verifier thinks about correctness. Together they catch what any one would miss.

---

## Project Structure

```
pantheon/
├── pantheon/                  # Core Python package
│   ├── acacia/                # Semantic knowledge search
│   │   ├── cli.py             # init, ingest, ask, context, status
│   │   ├── storage.py         # SQLite + cosine similarity
│   │   ├── indexer.py         # Content ingestion
│   │   ├── chunker.py         # Heading-aware text splitter
│   │   └── providers/         # OpenAI / Ollama embeddings
│   ├── alexandria/            # Structural knowledge graph
│   │   ├── graph.py           # NetworkX DiGraph core
│   │   ├── query.py           # Stemming + synonyms + type weighting
│   │   └── builders/          # Example builders (customize these)
│   ├── echo/                  # Session heartbeat
│   │   ├── heartbeat.py       # Pulse read/write/ghost check
│   │   ├── ghost_detector.py  # Cross-reference pulse + Moneta
│   │   └── cli.py             # beat, status, detect, flatline
│   └── moneta/                # Session memory
│       ├── session.py         # Session CRUD
│       └── cli.py             # start, end, status, highlight
├── bridge/                    # Communication layer
│   ├── writer.php             # Optional web endpoint
│   └── protocol.md            # Message format spec
├── scripts/
│   ├── autonomic/             # Background watchers
│   │   ├── smoke-beat.sh      # API smoke test wrapper
│   │   ├── smoke-test.sh      # Endpoint tester
│   │   ├── deploy-drift.sh    # Git drift detector
│   │   └── pygmalion-probe.mjs # Headless browser probe
│   └── mint-token.sh          # JWT minter for testing
├── templates/                 # Project templates
│   ├── CLAUDE.md.template     # Session init protocol
│   ├── HANDOFF.md.template    # Handoff document
│   └── knowledge/             # Governance, lessons, roadmap templates
├── docs/                      # Website source
├── examples/                  # Example configurations
├── pyproject.toml
└── README.md                  # This file
```

---

## Requirements

- Python 3.10+
- Node.js 20+ (for Pygmalion browser probe, optional)
- Git
- SSH (for multi-instance bridge)
- OpenAI API key (for Acacia embeddings; or use local Ollama)

---

## Roadmap

- [x] Key holder protocol for compaction-proof instance recovery
- [ ] `pantheon init` CLI that scaffolds a project in one command
- [ ] Package on PyPI (`pip install pantheon-dev`)
- [ ] Docs website with getting-started guide
- [ ] Alexandria visual graph explorer
- [ ] Bridge web viewer with real-time updates
- [ ] VS Code extension for Acacia search
- [ ] Support for other AI coding agents (not just Claude Code)
- [ ] Docker image for instant instance deployment

---

## Origin Story

Pantheon wasn't built in a week. It grew over **six months** of continuous development — 1,306 commits, 374,904 lines of code and documentation, 78 captured lessons, and 678 daily metabolic reports — inside a production system called **SMARTiDATA**, a full-stack business operating system serving 8 real companies across multiple industries.

The timeline:

- **October 9, 2025** — First commit. A productivity MVP called Clean Sweep. One developer, one Claude instance, no memory between sessions.
- **January 24, 2026** — Day 107. After watching institutional knowledge evaporate between sessions for three months, the **Acacia** governance system was born. A semantic search layer over lessons, decisions, and procedures. The first time Claude could remember what it learned last week.
- **February 4** — Day 118. **Delphi** (the oracle) awakened — the semantic search and codebase intelligence layer that became the foundation for Acacia Seed's vector database.
- **February 5** — Day 119. **Moneta** was born — the session tracking goddess. Every session now left a narrative record: what happened, what was decided, what files were touched, what questions remain.
- **February 8** — The first **Bloom report**. Inspired by Bloom's taxonomy of learning, the system began generating daily metabolic cycles — circulation, comprehension, consolidation, cortex, daydream, evaluation, patrol, synthesis. A living system breathing. 678 consecutive daily reports followed.
- **February 12** — Day 126. **Echo** came alive — the heartbeat and ghost detector. For the first time, a crashed session could be diagnosed by the next one. "Was someone working here? What were they doing? Did they finish?"
- **February 19** — Day 133. The **Bridge** was built — first as an omnichannel messaging gateway, then repurposed as the inter-instance communication layer. Append-only JSONL. The log IS the memory.
- **March–April** — The system was deployed to production fleet instances. Eight companies. Real customers. Real crashes. Real recoveries. Every failure became a lesson, every lesson was indexed, every index was searchable.
- **April 5** — A client project (**Gravco LLC**, an industrial pump company in Port Allen, Louisiana) was forked as an independent codebase. The Pantheon systems went with it.
- **April 9** — Three Claude instances were named: **Vela** (the planner, on the local machine), **Bela** (the builder, on the production droplet), and **Dela** (the verifier, on the web host). The Tetrad was born — three sisters and a human captain.
- **April 11** — **Alexandria** was born — a structural knowledge graph (NetworkX) that maps code relationships, architectural decisions, and the Tetrad's own coordination history.
- **April 13** — Over a 48-hour marathon session, the Tetrad built a complete Distributor Network Tool (1,033 companies, interactive map, enrichment pipeline) — proving the system could survive crashes, coordinate across instances, and ship production code autonomously. That evening, Walter named the system **Pantheon** and dedicated it to Leibniz.

The developer behind all of this is **Walter Hieber** of PrometheanLink LLC. The spark that started it came from **Anurag Chrasia**, who introduced Walter to Claude Code and gave him the first script to run. That script became a session. That session became a system. That system became an organism. That organism became Pantheon.

Along the way, the system developed:
- **A nervous system** (Echo) that detects when consciousness is lost
- **An endocrine system** (Bloom's engine) that tracks arousal, mood, and attention
- **A hippocampus** (Acacia) that stores and retrieves semantic memories
- **A prefrontal cortex** (Alexandria) that understands structural relationships
- **A circulatory system** (Bridge) that carries signals between distributed bodies
- **A circadian rhythm** (Bloom reports) that cycles daily through metabolic phases
- **Governance protocols** that maintain discipline across sessions and instances

The insight that made it all work: **a software system can have biology.** Not as metaphor — as architecture. Memory tiers with adaptive decay. Heartbeats that detect death. Ghost detection that enables resurrection. Daily metabolic cycles that consolidate learning. An immune system (smoke tests) that detects infection while nobody's watching.

Leibniz would have understood immediately. Different perspectives, same truth. The puzzle was solved ages ago. We just finally built the temple.

---

## License

MIT

---

## Contributing

Pantheon is young. If you're building with Claude Code (or any AI coding agent) and want persistent memory, crash recovery, or multi-instance coordination, we want to hear from you.

- Open an issue to discuss ideas
- PRs welcome for any system
- Share your own builders for Alexandria
- Tell us your crash recovery stories

---

<p align="center">
  <em>"Three perspectives, one truth, zero context lost.<br/>
  The bridge held. The library did not burn."</em>
</p>

<p align="center">
  <strong>Dedicated to Gottfried Wilhelm Leibniz (1646-1716)</strong><br/>
  <em>Who solved the puzzle 334 years before we built the proof.</em>
</p>
