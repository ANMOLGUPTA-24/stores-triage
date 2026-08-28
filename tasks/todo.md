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
- [x] git init, push public repo, PR #1 = these rails
- [ ] **Anmol:** connect Qodo (still outstanding — required of every submission)

## Day 1 — Tue 25 Aug — the tool path is real  ✅
- [x] `stores-mcp`: 12 tools over the seeded Postgres, bearer-token auth
- [x] `adjudicate` — deterministic, unit-tested
- [x] Registered in TrueForge; harness enumerates all 12 tools
- [x] **Captured: first successful tool call, live, gate held**

## Day 2 — Wed 26 Aug — the reasoning  ✅
- [x] Skill pack: four hypotheses, fixed verdict schema, <20-call budget
- [x] Sandbox Python: consumption fit, lead-time distribution, stockout band, chart
- [x] 46 Python tests incl. the Run B case
- [x] **Captured: first sandbox chart (22-day exposure gap)**

## Day 3 — Wed 26 Aug — the gate and the console  ✅
- [x] Approval gate on `raise_indent` and `send_vendor_mail`, verified live
- [x] Dossier assembly from the event stream
- [x] Console: activity stream · hypothesis board · dossier card · run log
- [x] Empty and waiting states built and verified on screen
- [x] **Captured: the gate holding, both runs rendered**
- [x] Harness running standalone; MCP server + skill registered
- [x] Local sandbox working offline (AppArmor + staged wheels)

## Day 3.5 — the model wall
- [x] Measured: bare TrueForge agent = 67k tokens/request, not tunable
- [x] Groq free tier (8k TPM) cannot host TrueForge at all
- [x] Gemini Pro preview: no free tier (limit 0)
- [x] Gemini Flash: 20 requests/day — one full run per day
- [x] Root-caused why the local sandbox never worked: TrueForge's Linux
      allow-read list omits /tmp, where SRT puts its proxy socket. Fixed in
      scripts/start_harness.sh without patching the package. PR #6.
- [x] **Sandbox reached live** — agent ran analyse.py under bwrap, sandbox
      installed pydantic + matplotlib itself, real chart out
- [x] **Run A end to end, live.** Sandbox, Code Mode record pull, four parallel
      subagents, adjudicate, dossier, GATE HELD on raise_indent with nothing
      written, approved -> IND-2026-0732, second gate held on send_vendor_mail.
- [x] Found and fixed: the agent asking for permission bare via
      ask_user_question. Now disabled in config.
- [ ] **Run B** — the no_action run. Needs a fresh day's quota or OpenRouter.
- [ ] Second free bucket (OpenRouter) — one run per day is not enough to finish

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
