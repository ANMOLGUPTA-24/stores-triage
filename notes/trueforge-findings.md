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

## Sandbox — Daytona *or* a local fallback the docs do not mention
- CORRECTION (26 Aug, from running v0.1.4): there is a **local sandbox fallback**
  (SRT) that needs host binaries `bwrap`, `socat`, `rg`. With those present it
  runs sandboxed code on this machine and **no Daytona key is needed**.
  The startup log says so:
      warn Local sandbox fallback is unavailable
           SRT host dependencies missing (linux: bwrap, socat, rg)
- `PUT /api/v1/settings/sandbox-providers` only accepts `type: "daytona"`, so the
  local fallback is not configurable - it activates when the host deps exist.
- Daytona remains the documented provider and needs an API key in Settings.
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

## Verified against a running harness (26 Aug, v0.1.4)
- Standalone: `npx @truefoundry/trueforge`, SQLite at
  ~/.local/share/trueforge/db, serves on http://localhost:8790, auth disabled.
- Registration is by API, not only the UI:
  - `POST /api/v1/settings/mcp-servers` with
    `{manifest:{type:"remote",name,url,description,auth:{type:"header",headers}}}`
  - `POST /api/v1/settings/skills` with
    `{manifest:{type:"git",name,url,path,ref,description}}`
  - `GET /api/v1/mcp-servers/{name}/tools` lists what the harness can actually see.
- `GET /api/v1/capabilities` reports `skill.enabled:false` while the sandbox is
  unconfigured - **skills require a sandbox**, so socat gates the skill too.

## Still unverified
- Daytona free-tier limits (may not matter now the local fallback exists).
- A remote HTTP MCP for Gmail/Slack that supports **sending** (not just reading).

## Context cost, measured (26 Aug, v0.1.4)

A bare TrueForge agent — no MCP servers, no skills — sends **67,358 tokens** on
its first request. Measured by letting Groq's 413 report the size:

| configuration | first request |
|---|---|
| preload all 12 stores tools + skill | 69,658 |
| deferred tools + skill | 68,887 |
| deferred tools, no skill | 68,681 |
| no MCP, no skill | 67,358 |
| everything off (sandbox, subagents, genUI, askUser) | 65,809 |

Our whole contribution is ~2.3k. The harness's own system prompt and built-in
tools are ~66k and are **not configurable** — every feature toggle together
moves it by ~1.5k.

Consequence for free tiers: the binding constraint is tokens-per-minute, and it
is not something an agent author can tune.

## Free-tier viability (26 Aug)

| provider / model | limit | verdict |
|---|---|---|
| Groq `openai/gpt-oss-120b` | 8,000 TPM (`on_demand`) | **unusable** — one request is 8x the per-minute ceiling, pacing cannot help |
| Groq `llama-3.3-70b-versatile` | Enterprise / contact sales | 404 on a free account |
| Gemini `gemini-3.6-flash` | 250K TPM, **20 requests/day** | usable at ~1 run/day if the run fits in <20 calls |
| Gemini `gemini-3.1-pro-preview` | `limit: 0` | no free tier at all |
