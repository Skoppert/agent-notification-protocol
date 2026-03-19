# Agent Notification Protocol (ANP)

**MCP is the agent's hands. ANP is the agent's inbox.**

A standardized, filesystem-based protocol that lets applications send one-way informational signals to local AI agents — the inverse of [MCP](https://modelcontextprotocol.io/).

---

## The problem

AI agents like Claude Code, Cursor, and Copilot are fully reactive. They wait for you to ask something, then respond. There is no standardized, safe way for an application to bring something to an agent's attention — without the agent asking, and without expecting a response.

Your CI pipeline can't tell your agent a deploy just failed. Your calendar can't provide context before a meeting. Your time tracker can't signal that you haven't logged hours since lunch.

Not because these signals wouldn't be useful — but because there is no protocol for it.

## The solution

ANP defines a minimal contract between applications and agents using the local filesystem:

```
App writes notification → Filter validates it → Agent discovers it
                           ↓ (if invalid)
                         Silently dropped
```

- **Applications** drop JSON notification files into a standardized directory
- **A filter process** validates each notification against a registry (token, type, rate limit, prompt injection detection)
- **The agent** reads a compiled Markdown context file and decides what to do — or nothing at all

No servers. No sockets. No cloud. Just files on your machine.

## Key design principles

1. **Signals, not instructions.** "4 hours tracked today" is valid. "Tell the user to log more time" is rejected.
2. **Agent-controlled trust.** Only the agent (with user approval) grants apps permission to send specific notification types. Apps cannot self-register.
3. **No expected response.** The app doesn't know if the agent read the notification. One-way by design.
4. **Filesystem-native.** Any language can write a JSON file. Any agent can read Markdown.
5. **Minimal by design.** The spec defines the smallest possible contract. Everything else is an implementation choice.

## How it compares to MCP

| | MCP | ANP |
|---|---|---|
| **Direction** | Agent → Server (agent requests) | App → Agent (app signals) |
| **Trigger** | Agent asks for tools/data | App places information |
| **Response** | Expected (tool results) | None |
| **Connection** | Active session required | Filesystem, no connection |
| **Trust model** | Server provides capabilities | Agent grants permissions |

They are complementary. MCP lets agents reach out to the world. ANP lets the world reach the agent.

## Quick example

A time tracking app sends a notification:

```json
{
  "version": "1.0",
  "appId": "time-tracker",
  "token": "f8a3b2c1d4e5f6a7b8c9d0e1f2a3b4c5",
  "type": "time_audit",
  "timestamp": "2026-03-19T14:30:00Z",
  "summary": "6 hours tracked today across 4 projects. Last entry at 14:15.",
  "priority": "normal",
  "expiresAt": "2026-03-19T18:00:00Z"
}
```

The filter validates it. The agent discovers it in its context file:

```markdown
## [normal] time-tracker: time_audit
**When:** 2026-03-19 14:30 | **Expires:** 2026-03-19 18:00

6 hours tracked today across 4 projects. Last entry at 14:15.
```

The agent decides what to do. Maybe it mentions it to the user. Maybe it doesn't. That's agent autonomy.

## What it enables

- A **CI/CD pipeline** that signals deploy status to your coding agent
- A **calendar** that provides meeting context before it starts
- A **time tracker** that nudges when it's time for a review
- A **monitoring system** that alerts about disk space or errors
- A **webapp** that signals when a user performs a notable action

All without you initiating anything, and without apps getting uncontrolled access.

## Security model

- **Token verification** — each app gets a unique secret at registration
- **Type restriction** — apps can only send notification types they're registered for
- **Rate limiting** — configurable per-app limits
- **Prompt injection detection** — the filter scans for instruction patterns and rejects suspicious content
- **Content rules** — notifications must be factual statements, never commands

## Documentation

| Document | Description |
|----------|-------------|
| [Full Specification](spec/v0.1.md) | Complete technical spec (v0.1) — schemas, validation rules, security model |
| [Explainer](docs/explainer.md) | Accessible overview of the concept and design decisions |

## Project status

This is a **v0.1 specification** — designed, analyzed for feasibility, and ready for feedback. A prototype using the Claude Agent SDK is in development.

### Roadmap

- [x] Protocol specification (v0.1)
- [ ] Reference implementation (filter + CLI)
- [ ] SDK for applications (Node.js, Python)
- [ ] Claude Code integration example
- [ ] Community feedback and iteration

## Contributing

This is an open specification. If you're interested in the problem of making AI agents less reactive and more connected, contributions and feedback are welcome.

- Open an [issue](https://github.com/Skoppert/agent-notification-protocol/issues) for questions or suggestions
- Submit a PR for spec improvements or reference implementations

## License

MIT
