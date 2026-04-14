# AI Procedures — YOUR_PROJECT

## Session Protocol

Every AI session MUST follow the session initialization protocol defined in
CLAUDE.md. The order matters:

1. Read the handoff (if any)
2. Reconcile git state
3. Harvest ghosts, start fresh moneta/echo beats
4. Check autonomic smoke results
5. Execute handoff first-move list

## The STOP Protocol

When you hit 3+ errors in a row, or find yourself trying "another approach":

1. **STOP** — Do not try another variation
2. **QUERY** — Check the knowledge base for relevant lessons
3. **DOCUMENT** — What exactly failed and why?
4. **INVESTIGATE** — Root cause, not symptoms
5. **REPORT** — Tell the human before proceeding

## Deployment Rules

- Never deploy without committing first
- Always verify the deploy with a health check
- If the health check fails, roll back before investigating
- Document every deploy in the Moneta session

## Knowledge Promotion

When you discover something non-obvious:

1. Create a Moneta highlight: `moneta highlight "description" --severity Important`
2. If it's reusable knowledge, promote it: `moneta promote highlights/file.md`
3. Rebuild Alexandria after adding lessons

## Multi-Agent Coordination

When working in a multi-agent setup:

- Always check your bridge inbox at session start
- Ack proposals and handoffs explicitly
- Long content goes in shared/topics/, not inline
- The captain's messages override all agent decisions

## File Safety

- Never modify files listed in CLAUDE.md's "Critical Files" without explicit
  human approval
- Always commit before making risky changes (gives a rollback point)
- Use Echo's `--scan` flag to track uncommitted files at risk
