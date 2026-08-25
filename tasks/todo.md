# Stores Triage — plan

Submission: **30 Aug 2026, 20:00 London.** Today is Tue 25 Aug. Six days.
Every item below advances a beat in CLAUDE.md §0b. Anything that doesn't, isn't here.

## Decisions taken (25 Aug)
- **Sandbox: Daytona.** Only provider TrueForge supports; §1 forbids hand-rolling one.
  Needs Anmol's own API key pasted into TrueForge Settings.
- **Mail: our own MCP server over real SMTP** to a mailbox we control, playing the
  vendor. No OAuth dance; the irreversible action stays entirely in our hands.
- **MCP transport: remote HTTP.** TrueForge does not do stdio, so we host
  `stores-mcp` ourselves. Providing a tool is not reimplementing the harness.
- **Console: TrueForge TypeScript SDK**, not the themed chat UI. §3 wants an
  operator console; the SDK's event stream (keyed by `threadId`) is what drives
  the hypothesis board.

## Day 0 — Tue 25 Aug — rails
- [x] Project constitution, folder, devlog
- [x] TrueForge research → `notes/trueforge-findings.md`
- [x] Postgres schema, five tables + run log
- [x] Synthetic seed: both runs indistinguishable from the alert alone
- [x] Verified: Run A 9.9 days to stockout / unconfirmed cover;
      Run B 10.2 days / real cover + duplicate indent
- [x] LICENCE, .gitignore, .env.example, README
- [ ] git init, push public repo, install Qodo, PR #1 = these rails
- [ ] **Anmol:** Daytona API key; SMTP app password; model provider key

## Day 1 — Wed 26 Aug — the tool path is real
- [ ] `stores-mcp`: HTTP MCP server over the seeded Postgres, bearer-token auth
  - [ ] read-only: `get_part`, `get_consumption_log`, `list_open_indents`,
        `list_consignments`, `get_vendor_lead_times`
  - [ ] gated writes: `raise_indent`, `send_vendor_mail`
  - [ ] `adjudicate` — deterministic, unit-tested, takes the four verdicts
- [ ] Register in TrueForge; agent calls it end to end
- [ ] **Capture: first successful tool call**

## Day 2 — Thu 27 Aug — the reasoning
- [ ] Root agent instructions: dispatch exactly four hypothesis subagents,
      fixed verdict + evidence schema
- [ ] Sandbox Python: consumption fit, lead-time distribution, projected
      stockout date with uncertainty band, chart
- [ ] Unit tests on adjudication + the maths, **including the Run B case**
- [ ] **Capture: first sandbox chart**

## Day 3 — Fri 28 Aug — the gate and the console
- [ ] Approval gate on `raise_indent` and `send_vendor_mail`
- [ ] Dossier assembly from the event stream (the harness gives the pause,
      the evidence is ours to gather)
- [ ] Console: live activity stream · hypothesis board · dossier card · run log
- [ ] Empty state and waiting state — they are most of the demo
- [ ] **Capture: first time the gate holds**

## Day 4 — Sat 29 Aug — Run B, polish, record
- [ ] Run B end to end; "no action" lands in the run log as an outcome
- [ ] Visual pass against §3: one accent colour, dense, monospace tool output
- [ ] README complete; Qodo evidence section filled with real PR links
- [ ] Storyboard against §0b, then **record in the evening**
- [ ] **Capture: first Run B "no action"**

## Day 5 — Sun 30 Aug — ship
- [ ] Cut the ~3 min video: problem → agent working → where the harness fits
- [ ] Write-up from `notes/devlog.md`
- [ ] Redaction check: no keys, no real names, no personal data in any frame
- [ ] **Submit Sunday morning**, not Sunday night

## Review
_(filled in as things land)_
