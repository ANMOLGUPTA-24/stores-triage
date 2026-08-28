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

## 2026-08-27 — rehearsal caught a real bug
- Quota had not reset at 10:00; a one-call probe consumed the last request, so
  Run A 429'd immediately. Should have launched the run directly — a 429 costs
  nothing, so the probe could only lose.
- Rehearsed the whole pipeline with no model: MCP tools, bwrap sandbox, chart,
  adjudicate. Both runs reach the correct verdict. Only the model's
  orchestration is now untested.
- Found while reading the rehearsal dates: _lands_in_time accepted an ETA in the
  past, so a consignment overdue and still in transit counted as cover. The
  agent would recommend no action citing a delivery that never arrived — the
  failure that idles a locomotive. Now requires 0 <= days_away <= horizon.
- Seed dates drift once the volume is old. Documented the re-seed and added it
  to the pre-recording checklist.

## 2026-08-28 (day 5, small hours) — the local sandbox never had network

- Re-seeded the database. Fresh ETAs: CN-8821 unconfirmed +2 days (Run A),
  CN-9104 in transit +3 days (Run B). The two runs still look identical from the
  alert alone, which is the whole demo.
- Merged PR #5 after Qodo's one finding. It flagged that the PR changed triage
  behaviour without naming a demo beat; writing that link down exposed a worse
  problem, which is that the storyboard pinned literal dates. It said CN-9104
  "lands 28 Aug" while the fresh seed says the 30th. Beats have IDs now and the
  dates are placeholders read off the database on the day.

- **Root-caused the sandbox failure that has been blamed on pip all week.**
  The story was "the sandbox has no network, so stage wheels and set
  PIP_NO_INDEX". Both halves were wrong.

  1. The harness builds the sandbox child env from scratch —
     `childEnv = {...commandEnv(...)}` — so `PIP_NO_INDEX` and `PIP_FIND_LINKS`
     set on the harness process never reach the sandbox at all. The wheelhouse
     was never being consulted. What was verified on day 3 was bwrap by hand,
     not the harness, so nobody noticed.
  2. The sandbox is *supposed* to have network: `pypi.org` and
     `files.pythonhosted.org` are both on TrueForge's own allowed-domain list.

  The real fault is a filesystem/network mismatch. SRT reaches its filtering
  proxy over a Unix socket at `os.tmpdir()/claude-http-<id>.sock`, but
  TrueForge's `ALLOW_READ_BY_PLATFORM.linux` does not include `/tmp`. The
  sandboxed process cannot see the socket, so every connection dies with
  `Proxy CONNECT aborted`, so `pip install pydantic` — the first thing a sandbox
  does — always fails. On Linux the local sandbox cannot start, and skills go
  with it, because skills require a sandbox.

  Proved it rather than guessed it: drove SRT's own CLI with TrueForge's exact
  filesystem policy. `allowRead: ["/"]` gives `pypi HTTP 200`; the harness's real
  policy gives `Proxy CONNECT aborted`; adding `/tmp` to the same policy gives
  `HTTP 200` again. Three runs, one variable, no model involved.

- Fixed without patching the package. TrueForge adds one more path to allow-read
  at runtime: the Code Mode socket parent, which it computes as
  `os.tmpdir()/tf_cms` and then realpath()s. Set `TMPDIR` to a short directory we
  own and make `tf_cms` inside it a symlink back to its own parent, and the
  allowed path becomes `TMPDIR` itself — which is where the proxy socket lives.
  The link has to be made after boot, because TrueForge rm -rf's that path on
  startup and only reads it when the first sandbox is created. All of it is in
  `scripts/start_harness.sh` with the reasoning written above it.
- Cost of finding this the expensive way: **fifteen** model requests out of the
  day's twenty, spent on an agent retrying a sandbox that could never come up.
  (I first said six; counting `model.message` events in the session put it at
  fifteen for the broken run and six for the good one, which is the whole day.)
  A watchdog now kills a run on the first `Sandbox initialization failed`, so a
  broken sandbox costs one request instead of six.

- **First live run that reached the sandbox.** `*** SANDBOX UP ***` at 19s, then
  the skill read, `get_part`, `get_consumption_log`, `get_vendor_lead_times`,
  `input.json` written, and `analyse.py` run inside bwrap. The sandbox installed
  pydantic *and* matplotlib from pypi on its own, which is the proof the network
  fix is real and not a story.

  Numbers computed in the sandbox, not by the model:

      mean_daily_draw        4.48/day     over 120 observed days
      days_to_stockout       9.4  (p10 7.7, p90 11.4)
      lead_time_p50 / p80    23.0 / 29.8  over 14 completed orders
      vendor_runs_late       true         (promised 21)
      spike_days             []           so consumption_spike has nothing to stand on

  Chart written and recovered to `notes/evidence/runA-chart.png`: a 20-day
  stretch with no stock between running dry and the vendor delivering. That gap
  is the argument for ordering now, and it is drawn rather than asserted.

- Then 429: 20 requests/day exhausted, about six of them wasted on the broken
  sandbox before the watchdog existed. The run stopped one step before
  dispatching the four subagents.
- The storyboard said "~22-day gap"; the fresh seed makes it 20. Made that a
  placeholder too - the chart prints the number, so read it off the chart.

## 2026-08-28 (day 5) — what the first live run exposed

Reading the run back was worth more than the run.

- **The agent retyped all 119 consumption rows into a heredoc.** It had just read
  them out of `get_consumption_log` and typed them again into a Python literal.
  I diffed the transcription against the database expecting to find the bug that
  explained a number mismatch. It was byte-perfect: 119 rows, same total, no
  duplicates. So the model copied it correctly this time - but the design still
  routes every row of evidence through the one component that is not allowed to
  be the source of a number, and nothing would have caught it if it had slipped.

  Fixed properly: the sandbox now fetches its own record over Code Mode.
  TrueForge drops an MCP client into the sandbox and points `TFY_MCP_SOCK` at it,
  so `analyse.py --part-no TRB-4417 --days 120` pulls the part, the log and the
  lead times itself. The record never passes through the model at all, and steps
  1 and 2 of the skill collapse into one call.

- **The real cause of the mismatch was a clock.** The sandbox reported 4.48/day
  and the same code on the host reported 4.45/day from identical rows. Three
  different notions of "today" were in play:

      Postgres (container, UTC)   2026-08-27
      sandbox (UTC)               2026-08-27
      host / MCP server (IST)     2026-08-28

  Every date in this system is relative to Postgres `CURRENT_DATE` - the seed,
  the consumption window, the ETAs, the indent numbers - but `analyse.py`
  rebuilt its window from the local clock and `adjudicate` compared ETAs against
  `date.today()` on the host. For the five and a half hours a day that IST and
  UTC disagree, adjudication was a day ahead of the data. After the overdue-cover
  fix that skew points the wrong way: it discards cover that is still valid, so a
  demo recorded late in the evening could have flipped Run B into an indent.

  There is one source of truth now, `db.today()`, and `get_consumption_log`
  returns the exact `window_start` / `window_end` it queried so the sandbox fits
  over the window that was actually asked for.

- Found while fixing that: `consumed_on >= CURRENT_DATE - 120` spans **121**
  calendar days, so a 121-day total was being divided by a 120-day denominator.
  Strict `>` now, and `days` means exactly that many days ending today.

- Host and sandbox now agree exactly: 4.48/day either side. Model-free rehearsal
  of both runs against the real MCP server:

      TRB-4417  4.48/day, p50 9.4d, lead p80 29.8d -> RAISE_INDENT (critical, 200)
                counterfactual names CN-8821, ETA 2026-08-29, unconfirmed
      BRK-2290  5.79/day, p50 9.5d, lead p80 23.0d -> NO_ACTION
                cites CN-9104, in transit, due 2026-08-30

  9.4 against 9.5 days. Still indistinguishable from the alert alone, which is
  the entire premise of the demo.
- 65 tests.

## 2026-08-28 (day 5, afternoon) — Run A end to end, and the gate holds

- Merged the sandbox and Code Mode work, restarted the harness so it re-cloned
  the skill, and ran Run A live. The sandbox came up in 18s and `analyse.py`
  pulled the part, the log and the lead times itself. **The record never passed
  through the model.**
- **All four subagents dispatched at once**, each made its one tool call, each
  returned a verdict. First time the hypothesis board has been real.
- Then a 429 - but `limit: 5`, which is the per-*minute* rate, not the daily
  twenty. Four subagents at once is eight requests in ten seconds and the
  harness has no backoff, so the turn dies about four requests short of the
  gate. **A full Run A cannot fit in one turn on Gemini's free tier.** Not a
  quota problem, a burst problem.
- The session survives it with the verdicts intact, so the rest was driven as a
  second, sequential turn: `adjudicate` -> `raise_indent`, `draft_indent` for the
  payload. Two more scripts, `resume.mjs` and `approve.mjs`.
- **Then the agent asked for permission bare.** It called `ask_user_question`
  with "Do you approve raising an indent of 200 nos for part TRB-4417 and
  sending the draft order email?" - no evidence, no payload, no counterfactual,
  and no held call for the harness to gate. A confirm() box with the dossier
  deleted, produced at the exact moment the design exists to prevent it. Qodo
  caught a version of this before and the skill wording was fixed; the model
  just found another route. It is config now: `askUserQuestions.enabled = false`,
  so the only way to reach a human is to call the gated tool.
- **GATE HELD** on `raise_indent{part_no: TRB-4417, qty: 200}` with nothing
  written - no indent, no run-log row. Approved it, and:

      raise_indent -> IND-2026-0732 raised 2026-08-28
      SECOND GATE   -> send_vendor_mail{indent_no: IND-2026-0732,
                                        needed_by: 2026-08-28, qty: 200}

  The mail is gated separately, so approving the indent did not pre-approve it,
  and the `indent_no` it carries is the one `raise_indent` actually returned.
  Stopped there rather than sending mail.
- 19 of 20 requests for the day. Run B still to do.

## 2026-08-28 (day 5, evening) — Run B, and a model bake-off nobody planned

- Set up OpenRouter. The free tier is 20 requests/minute and 50/day against
  Gemini's 5 and 20, and it was the per-minute number that mattered: four
  subagents at once is eight requests in ten seconds.
- Three models, three different failures, which turned into a useful finding:

      nemotron-3-ultra  ignored the skill completely. No subagents, no
                        analyse.py, no adjudicate - it fetched the evidence
                        itself and tried to write its own numpy analysis in a
                        heredoc. Also "Service temporarily overloaded" twice.
      glm-5-2           upstream 429 within one second, twice.
      minimax-m3        read SKILL.md and the scripts first, then followed the
                        procedure exactly.

  Worth saying plainly: the deterministic core does not care which model runs,
  but whether the *demo* works depends entirely on the model following the
  skill. Gemini did, MiniMax did, Nemotron did not. That is a model-selection
  finding, not a prompt one - the skill text was identical in all three.

- **Run B, live, one unbroken turn, 101 seconds:**

      analyse.py in the sandbox -> four subagents at once ->
      adjudicate -> no_action

      reason      BRK-2290 is already on order. Indent IND-2026-0731 is open
                  and consignment CN-9104 (300 nos) is in transit, due
                  2026-08-30, inside the 8-day stockout window.
      ruled out   consumption_spike, bom_change
      change      If CN-9104 slips past 2026-08-30 or is short-shipped, this
                  becomes a genuine shortage.

  **NO GATE.** Nothing to approve, because nothing should happen. `run_log`
  holds one row, `BRK-2290 | no_action`, and no new indent was raised.

  Both runs are now real: TRB-4417 raises and holds at the gate, BRK-2290 does
  nothing and says why. From the alert alone they were the same problem.
