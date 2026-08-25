# Devlog

Two lines per session: what was built, what broke.

## 2026-08-25
- Project constitution written to CLAUDE.md; repo folder created.
- Nothing broken yet.
- Researched TrueForge: subagents parallel via create_sub_agent, approval event carries payload only, Daytona-only sandbox, remote-HTTP-only MCP, UI via TS SDK. Findings in notes/trueforge-findings.md.
- Nothing broken; no code written yet.

## 2026-08-25 (day 1)
- stores-mcp built: 12 tools over real Postgres, bearer auth, destructiveHint on
  the two irreversible ones. Adjudication is deterministic code with 20 tests.
- Both runs verified end to end over MCP before any model is involved: TRB-4417
  raises (counterfactual names CN-8821), BRK-2290 says no action (cites the
  indent and the consignment).
- Fixed: ruled_out counted "inconclusive" as ruled out. It does not - an
  undecided subagent has dismissed nothing.
