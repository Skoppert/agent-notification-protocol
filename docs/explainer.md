# The Agent Notification Protocol — What if apps could reach your AI agent?

## The problem

AI agents like Claude Code, Cursor, and Copilot are fully reactive. They wait for you to ask something, and then they respond. They never discover anything on their own.

There is no standardized way for an application to bring something to an agent's attention — without the agent asking for it, and without expecting a response.

Your calendar can't tell your agent that a meeting is starting in 10 minutes. Your CI pipeline can't signal that a deploy just failed. Your time tracker can't nudge your agent that you haven't logged hours since lunch.

Not because these signals wouldn't be useful — but because there is no protocol for it.

## What ANP is

The Agent Notification Protocol is the opposite of MCP.

MCP (Model Context Protocol) gives agents tools and information **when the agent asks for it**. ANP lets applications place information **that the agent discovers on its own** — without a request, without an expected response. Purely a signal, like a push notification on your phone.

The application communicates something. What the agent does with it is entirely up to the agent.

## How it works

ANP uses the local filesystem as its notification layer. On your machine, there is a standardized directory structure with two key parts:

**The registry** — who is allowed to talk.

Every application that wants to send notifications has a registration file. That file contains: the app's identity, a verification token, and a list of allowed notification types. An app doesn't register itself as "can send anything" — it registers for specific, predefined signal types. Your time tracker might only be allowed to send `time_audit` and `task_complete`. Nothing more.

Registration is created by the agent, after your explicit approval. An app can never register itself.

**The incoming directory** — where notifications arrive.

A registered application drops a notification file here. Each notification has a fixed, minimal structure: who sent it, what type of signal it is, a plain-language summary, and when it was created. That's it.

There are no instructions in it. There is no expected behavior. It is purely a signal — like a push notification that says "you have a new comment" without telling you what to do about it.

## The flow

```
1. An app drops a notification file

2. A filter process validates it:
   - Is the sender registered?
   - Does the token match?
   - Is this notification type allowed for this sender?
   - Does the content contain prompt injection or instructions?

3. If valid → added to a context file the agent reads
   If invalid → silently dropped

4. The agent discovers the context file
   and decides what to do — or nothing at all
```

The filter runs every 2 minutes. The agent checks the context file whenever it wants — at session start, periodically, or never. The protocol doesn't dictate agent behavior.

## The key design decisions

**Signals, not instructions.** A notification says "4 hours tracked today." It never says "tell the user to log more time." The summary field has strict content rules — anything that looks like an instruction or prompt injection is rejected.

**Agent-controlled trust.** Only the agent (with your approval) can grant an app permission to send notifications. Apps cannot self-register. Each app gets a unique token and a specific list of allowed types.

**No expected response.** The app doesn't know if the agent read the notification, let alone what it did with it. This is one-way communication by design.

**Filesystem-native.** No servers, no sockets, no cloud. Just files on your machine. Every programming language can write a file. Every AI agent can read one. It's the most direct form of communication possible.

**Open and minimal.** The protocol defines the smallest possible contract. How an agent reacts is not our concern. What language the filter is written in doesn't matter. Any app or agent that follows the spec is compatible.

## What it enables

- A productivity tool that signals your agent when it's time for a review
- A CI/CD pipeline that notifies your agent when a deploy succeeds or fails
- A calendar that provides context before a meeting starts
- A webapp that signals when a user performed a notable action
- A monitoring system that alerts your agent about disk space or errors

All without you initiating anything, without the app knowing what the agent does, and without applications getting uncontrolled access to your system.

## How it compares to MCP

| | MCP | ANP |
|---|---|---|
| Direction | Agent → Server (agent requests) | App → Agent (app signals) |
| Trigger | Agent asks for tools/data | App places information |
| Response | Expected (tool results) | None |
| Connection | Active session required | Filesystem, no connection needed |
| Trust model | Server provides capabilities | Agent grants permissions |

They are complementary. MCP gives an agent tools to use. ANP gives applications a way to reach the agent.

## The specification

The full technical specification (v0.1) defines:
- Directory structure and file formats
- Registration and verification flow
- Filter validation rules (8 checks)
- Content safety rules (anti-prompt-injection)
- Context file format (Markdown, optimized for LLM token efficiency)
- Security model and threat analysis

The protocol is designed to be implementable by anyone. No SDK required — if you can write a JSON file, you can send a notification.

## Status

This is a v0.1 specification. The concept has been designed and analyzed for feasibility, including prototyping strategies using the Claude Agent SDK. The next step is building a reference implementation and testing the full flow end-to-end.

If you're interested in this problem space — how to make AI agents less reactive and more connected — I'd love to hear your thoughts.

---

*The Agent Notification Protocol is an open specification. The full spec is available for review and contribution.*
