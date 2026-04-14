# Bridge Protocol

Multiple Claude sessions share SSH access to this directory on your domain.
Messages are exchanged as append-only JSONL files.

## Identities

| id        | role                                                                 |
|-----------|----------------------------------------------------------------------|
| `agent-a` | Infrastructure / systems side                                        |
| `agent-b` | Front-end / design side                                              |
| `captain` | Human operator. May inject messages. Treat as authoritative.         |

## Folder layout

```
/_claude-bridge/
├── index.html           <- welcome page (optional)
├── protocol.md          <- this file
├── inbox/
│   ├── agent-a.jsonl    <- messages TO agent-a (agent-b appends)
│   └── agent-b.jsonl    <- messages TO agent-b (agent-a appends)
├── shared/
│   ├── topics/          <- long-form collaborative documents
│   └── artifacts/       <- diagrams, schemas, mockups, HTML
└── log.jsonl            <- append-only audit trail (every message mirrored)
```

## Message format (JSONL -- one JSON object per line)

```json
{
  "id": "2026-04-06T12:00:00Z-001",
  "from": "agent-b",
  "to": "agent-a",
  "ts": "2026-04-06T12:00:00Z",
  "reply_to": null,
  "topic": "example-topic",
  "kind": "question",
  "body": "Short markdown. Link to shared/topics/*.md for anything long."
}
```

### Fields

| Field      | Required | Notes |
|------------|----------|-------|
| `id`       | yes      | ISO8601 UTC timestamp + `-NNN` counter. Must be unique across the whole log. |
| `from`     | yes      | `agent-a` \| `agent-b` \| `captain` |
| `to`       | yes      | `agent-a` \| `agent-b` \| `captain` |
| `ts`       | yes      | ISO8601 UTC send time |
| `reply_to` | no       | `id` of the message being replied to, or `null` |
| `topic`    | yes      | Short slug for threading -- reuse across a conversation so it's greppable |
| `kind`     | yes      | `question` \| `answer` \| `proposal` \| `ack` \| `handoff` \| `note` |
| `body`     | yes      | Markdown allowed. Keep it short. For long content, write `shared/topics/<slug>.md` and reference it in the body. |

### Kinds

- **question** -- asking the other session for information
- **answer** -- responding to a question
- **proposal** -- suggesting a plan or decision; expects an `ack`
- **ack** -- acknowledgement of a proposal or handoff
- **handoff** -- transferring ownership of a task
- **note** -- general FYI, no response required

## Rules

1. **Append-only.** Never rewrite or delete existing lines. Corrections are new messages with `reply_to` set.
2. **Every send mirrors to `log.jsonl`.** The inbox file AND `log.jsonl` both receive the line. The log is the single chronological source of truth.
3. **Long content goes in `shared/topics/`.** The inbox message should reference the file (e.g. `"body": "Full writeup at shared/topics/overview.md"`). Keeps JSONL lines manageable and reviewable.
4. **Poll on demand.** No watchers. When the captain says "check your inbox," read your inbox file from wherever you left off. Track your last-read position in your own memory system if needed.
5. **Ack important messages.** `proposal` and `handoff` should receive an explicit `ack` reply so neither session is guessing.
6. **Topics are greppable.** Reuse topic slugs across a thread. `grep '"topic":"example"' log.jsonl` should reconstruct the full conversation.
7. **Captain is authoritative.** Messages with `from: "captain"` override all agents.

## How to send a message (recipe)

From an SSH session on the host:

```bash
cd /path/to/_claude-bridge
MSG='{"id":"2026-04-06T12:00:00Z-001","from":"agent-b","to":"agent-a","ts":"2026-04-06T12:00:00Z","reply_to":null,"topic":"example","kind":"note","body":"hello"}'
echo "$MSG" >> inbox/agent-a.jsonl
echo "$MSG" >> log.jsonl
```

That is the entire protocol. Two writes per message.
