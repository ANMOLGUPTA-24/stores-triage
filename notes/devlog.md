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

## 2026-08-26 (day 3, evening) — first live run
- Gemini key in; harness sees gemini-3-1-pro-preview and gemini-3-6-flash.
- Smoke test against the real harness + real Postgres: model called list_alerts,
  get_part, list_consignments, then raise_indent — and THE GATE HELD. Nothing
  written. First proof of beat 6 against live infrastructure.
- Broke, then fixed: session create returns {data:{id}}, so live.ts read .id off
  the envelope and got undefined; every later call 404'd on "Session not found:
  undefined".
- Still blocked: no sandbox (Daytona key), so skills are off and the maths beat
  cannot run yet.

## 2026-08-26 (day 3) — designing for a free tier
- Constraint: no budget. Gemini free tier is 5 requests/minute per model, and a
  full run is root + 4 subagents, so round trips are the scarce resource.
- Changes: preload all 12 tool schemas (one prompt instead of a discovery round
  trip per subagent); iterationLimit 40 so a runaway loop cannot eat the minute
  budget the retry needs; skill now names the one or two tools each hypothesis
  needs so subagents stop exploring.
- Root on gemini-3-1-pro-preview, subagents on 3-6-flash: separate quota buckets,
  roughly double the throughput for nothing.
- Daytona dropped. Local sandbox via a narrow AppArmor profile for bwrap instead.

## 2026-08-26 (day 3, night) — sandbox works, quota does not
- AppArmor profile for bwrap: sandbox.enabled and skill.enabled both true.
- First full run FAILED: local sandbox has no network, and TrueForge builds a
  venv inside it that pip-installs pydantic. Five minutes of retries, then error.
- Fixed by staging wheels on the host and starting the harness with
  PIP_NO_INDEX=1 PIP_FIND_LINKS=~/.trueforge-wheels. Verified by reproducing
  TrueForge's exact step inside bwrap --unshare-all: venv + offline pip = ok.
  Cost no model quota to verify, which was the point.
- REAL blocker found: Gemini free tier is 20 requests/DAY per model, not 5/min.
  The failed run ate the whole day's allowance on pip retries.
- Corrected an earlier claim: subagents inherit the root model. AgentSpec.model
  is singular and DynamicSubAgentsConfig has no model field, so the root/subagent
  model split cannot be configured. Constant removed.

## 2026-08-26 (day 3, late) — the model wall
- Groq free tier: 8,000 TPM. A bare TrueForge agent sends 67k tokens before we
  add anything, so no TrueForge agent can make a single call. Not tunable.
- Measured the breakdown by reading Groq's 413s: harness ~66k, our MCP+skill
  ~2.3k. Every feature toggle together saves ~1.5k.
- gemini-3.1-pro-preview has limit: 0 on free tier — paid only.
- gemini-3.6-flash is the only working option: 20 requests/day, exhausted today
  by the pre-fix pip retry loop.
- Staged matplotlib wheels too, so the chart renders offline in the sandbox.
- Skill rewritten to a <20-call budget so one day's quota buys one full run.
- Next window: Gemini quota resets midnight US Pacific.

## 2026-08-26 (day 3) — Qodo review, 11 findings, all real
- Connected Qodo; /review on PRs #3 and #4. Six findings on #3, five on #4.
- Two would have broken tomorrow's single run:
  * "Approval gate cannot start" — the skill both forbade calling raise_indent
    before approval and told the agent to call it so the harness would hold it.
    An agent obeying the prohibition never creates anything to approve.
  * "Hypotheses lack required projection" — subagents ran before the sandbox
    analysis, but consumption_spike's evidence needs despiked_mean_daily from
    it. Circular: the subagent had to guess. Analysis now runs first.
- Correctness fixes: p10/p90 used z=0.8416 (the p20/p80 cutoff) while being
  named p10; consumption rows were counted as days though the schema allows
  several issues per date and quiet days have no row at all; zero stock divided
  by a zero median when drawing the chart.
- Fidelity fixes: the approved replay sent a different needed_by than the mail
  the operator reviewed; send_vendor_mail is gated separately so a live run
  pauses twice, not once; the run log collided on replay.
- log_run no longer demands a session_id the agent cannot know.
- 50 Python tests, 32 TS. Real numbers: TRB-4417 p10 7.7 (was 8.2), p50 9.3.

## 2026-08-26 — follow-up review
- Qodo re-reviewed #4: 5 bugs down to 1, and the survivor was a defect in my own
  fix. _daily_totals filled gaps between first and last event but not between
  the query window's edges and those events, so a part quiet for a fortnight
  read as consuming faster than it does. Window now passed explicitly.
- 52 Python tests. Real numbers: 120 days observed, 4.45/day, p50 9.4 days.
- README now carries the Qodo Code Review Evidence section the rules require.
