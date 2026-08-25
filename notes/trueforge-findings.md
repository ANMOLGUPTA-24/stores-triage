# TrueForge — what the harness actually gives us

Researched 25 Aug 2026 from https://trueforge.dev (docs) + repo README.
MIT, launched 19 Aug 2026. Run local: `npx @truefoundry/trueforge@latest` (SQLite),
or hosted (Postgres + Redis, Docker Compose / Helm).

## Subagents — fits §0a, but identity comes from the prompt
- Built-in `create_sub_agent` tool. Root agent generates instructions per subtask
  at runtime. **Runs concurrently; root waits for all.**
- Subagents inherit the root's MCP tools + sandbox.
- One level deep (no nesting). Subagents cannot ask the user questions.
- **No pre-registered named subagents.** Our four hypotheses are enforced by the
  root agent's instructions, not by config.
- Each subagent gets its own `threadId` in the event stream; root is `"main"`.
  -> this is what drives the hypothesis board.

## Approval gate — the dossier is ours to build
- Turn pauses, emits `tool.approval_required` with `tool_calls[]`
  (`id`, `source_event_id` -> the `model.message` holding tool name + args)
  and `thread_id`. `turn.done` then carries `state.required_actions`.
- Resume = new turn with `user.tool_approval` items:
  `{ threadId, toolCallId, approval: { status: "allow" | "deny", reason } }`.
- **The event carries the payload, not the evidence.** Chart, verdicts, and the
  what-would-change-my-mind line must be assembled by us from earlier stream
  events and rendered in our own card. The harness gives us the *pause*; §0a is
  our contribution on top of it.

## Sandbox — Daytona only, external API key
- Daytona is the only provider today. Requires a Daytona API key in Settings.
- No local/offline sandbox option documented.
- Sandbox is a tool, provisioned on demand; code/files/shell. Secrets stay in
  the harness, not the sandbox.
- Files come back via `GET` download-a-file-from-the-turn-sandbox -> chart retrieval.

## MCP — remote HTTP only
- Register a **remote URL**. Auth: none / static headers / OAuth.
- **No stdio transport documented.** A local stdio Postgres MCP will not attach.
- Implication: we expose our own HTTP MCP server (read-only query tools +
  `raise_indent` + `send_vendor_mail`) over the seeded Postgres. That is a tool,
  not harness reimplementation — §1 is not violated.

## UI — SDK, not a theming job
- Bundled chat UI ships with the server; `@truefoundry/trueforge-ui` publishes it
  as an embeddable React component with themes and layouts.
- Containers are composable into a custom layout: `ToolApprovalContainer`,
  `ToolCallContainer`, `AgentStepsContainer`, `AskUserContainer`, `Thread`, etc.
- No documented headless hook for raw stream events.
- For §3 (operator console, not a chat) the cleaner path is the **TypeScript SDK**
  (`client.sessions.createTurnStream`) in our own React app, rendering the four
  surfaces off the event stream keyed by `threadId`.

## Still unverified
- Daytona free-tier limits.
- A remote HTTP MCP for Gmail/Slack that supports **sending** (not just reading).
