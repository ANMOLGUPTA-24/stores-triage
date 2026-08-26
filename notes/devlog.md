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

## 2026-08-26 (day 2)
- projection.py: draw-rate fit with spike detection, empirical lead-time
  percentiles, stockout band solved from mean*t +/- z*sd*sqrt(t). Stdlib only so
  it runs in a bare sandbox. 26 more tests, 46 total.
- Real seeded data gives TRB-4417 a 9.3-day stockout against a 31-day p80 lead
  time. The constitution guessed "~9 days" and the data agrees.
- Skill pack written; analyse.py runs it in the sandbox and draws the chart.
  Chart redrawn to shade the 22-day exposure gap - that gap is the argument.
- Broke, then fixed: first chart put the legend on top of the lead-time line and
  never drew the gap at all.
- Qodo still not installed. PRs #1 and #2 merged unreviewed.

## 2026-08-26 (day 3)
- Operator console built: four surfaces, one accent colour used only for
  blocked-on-human. Reducer folds the TrueForge event stream; verdicts are read
  from adjudicate's arguments, not from subagent prose. 32 TS tests.
- Runs against a recorded event stream so the waiting states are real.
- Broke, then fixed, both found by actually driving the UI:
  1. Approve button sat below the fold and the payload's own scrollbar ate the
     wheel. Action bar is now sticky.
  2. turn.done latched "blocked" forever, so the console still claimed it needed
     a human after the indent was raised. An approval is now pending only until
     its tool call returns.
- Run A and Run B both verified on screen. Screenshots captured for the video.

## 2026-08-26 (day 3, later)
- Harness running standalone on :8790. Registered stores-mcp (authenticated) and
  the skill by API; harness enumerates all 12 tools. First real harness-to-tool
  connection.
- Found: TrueForge has an undocumented LOCAL sandbox fallback needing bwrap +
  socat + rg. Only socat is missing here, so Daytona is off the critical path.
- Blocked on: socat (needs sudo), and a model provider key.
