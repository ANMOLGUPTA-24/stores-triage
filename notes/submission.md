# Submission write-up — Stores Triage

Every number here comes from a live run, not from memory. Both runs have been
executed end to end against the real harness, the real MCP server over Postgres,
and a real sandbox.

---

## Try it before reading any of this

**https://anmolgupta-24.github.io/stores-triage/** — no install, no account. The
operator console replaying both runs, one event at a time. Click `TRB-4417` to
watch it stop at the approval gate with the working attached; click `BRK-2290`
to watch it correctly do nothing. About a minute for both.

## One line

An agent that decides whether a spare-part stock alert is a real shortage or a
paper one, and is trusted to answer "do nothing" because the reasoning is code
you can read.

## The problem

A locomotive works runs on reorder levels. A part drops below its level and an
alert fires. The stores officer then has to answer a question the alert cannot:
**is this real?**

The evidence lives in three places that do not talk to each other — the
consumption log, the open indents, and the consignments in transit. So the
officer either raises the indent to be safe, or lets it sit.

Both mistakes cost:

- **Raise a duplicate indent** against stock already in transit and the works
  pays expedite rates on stock it already owns.
- **Miss a real shortage** and a locomotive sits idle.

The demo is built on two alerts that are **indistinguishable from the alert
alone** — TRB-4417 at 42/60 and BRK-2290 at 55/80, both about nine days from
running dry. One is real. One is not.

## What it does

Four competing explanations for why the shortage might be on paper only, one
subagent each, dispatched in parallel:

| hypothesis | the claim it tests |
|---|---|
| `consumption_spike` | a one-off burst tripped the level, not the steady rate |
| `inbound_delay` | stock is already coming, just not booked in |
| `duplicate_indent` | someone already raised this and it is still open |
| `bom_change` | the part is superseded and the works is moving off it |

Each subagent is trying to prove the shortage is **not** real. Ruling all four
out is what makes it real. It is differential diagnosis, not a task list.

## The three decisions that make it trustworthy

### 1. The verdict is not the model's opinion

`adjudicate` is ordinary Python with unit tests. Four ordered rules, each of
which states why it fired. The agent gathers evidence and calls tools; it does
not get a vote on the answer. The skill says so explicitly: *"Do not overrule
it. If you disagree with its answer, your verdicts were wrong."*

That is what lets Run B pass in CI **with no model involved at all**.

### 2. No number comes from the model

Every figure — draw rate, stockout band, lead-time percentiles — is computed by
`analyse.py` running in the harness sandbox. The stockout band is solved rather
than guessed: cumulative draw over `t` days has mean `μt` and standard deviation
`σ√t`, so the band comes from solving `μt ± zσ√t = stock` for `√t`. A flat
percentage haircut on the median would have been easier and wrong.

The standing instruction is: *"If you are about to write 'roughly' or
'approximately' in front of a figure, you have skipped a step."*

### 3. The gate carries a dossier, not a confirm() box

`raise_indent` and `send_vendor_mail` carry `destructiveHint`, so TrueForge holds
them. What we built is what the human sees while it is held:

1. the recommendation and the reason
2. all four verdicts with the evidence that produced each
3. the numbers, and the chart showing the gap between running dry and the vendor
   delivering
4. the **exact payload** — the indent fields and the full mail body, verbatim
5. `what_would_change_my_mind`, generated from the rule that *almost* fired

That last line is the one we are proudest of. It is not the model being
reflective — it comes from the near-miss mechanism in `adjudicate`, so it is
always specific and always checkable. On Run A it reads: *if CN-8821 is confirmed
and lands by its ETA, do not raise this indent.*

An approval is only worth something if the human can check it in five seconds.

## The result that matters

Two alerts, indistinguishable from the alert alone — **9.4 days** of stock
against **9.5**. Both were run live.

**Run A — TRB-4417.** Sandbox up in 18s; `analyse.py` pulls the record itself
and computes 4.48/day, dry in 9.4 days (7.7 at the fast end) against a 29.8-day
p80 lead time — a 20-day stretch with no stock. Four subagents, four verdicts,
`raise_indent` recommended. The harness holds the call:

    *** GATE HELD ***    raise_indent{part_no: TRB-4417, qty: 200}
                         nothing written: no indent, no run-log row
    approved          -> IND-2026-0732
    *** SECOND GATE ***  send_vendor_mail{indent_no: IND-2026-0732}

Approving the indent does not pre-approve the mail, and the `indent_no` the
second gate carries is the one `raise_indent` actually returned.

**Run B — BRK-2290.** One unbroken turn, 101 seconds:

    action    : no_action
    reason    : BRK-2290 is already on order. Indent IND-2026-0731 is open and
                consignment CN-9104 (300 nos) is in transit, due 2026-08-30,
                which is inside the 8-day stockout window. Raising another
                indent would duplicate stock the works has already bought.
    ruled out : consumption_spike, bom_change
    change    : If CN-9104 slips past 2026-08-30 or is short-shipped, this
                becomes a genuine shortage.

**No gate. No Approve button. No amber anywhere.** Nothing to approve, because
nothing should happen — and the run log records `no_action` as an outcome, not
an error. No new indent was raised.

Most agent demos cannot do this; they are built to act, so doing nothing looks
like failure. Being confidently right that nothing should happen is the harder
half of the problem, and it is the half that saves the money.

## How it is wired

```
stock alert
   │
   ├─ TrueForge harness ────────────────────────────────────────────────┐
   │    agent loop · MCP client · sandbox · subagent threads · gates    │
   │                                                                    │
   │  skill: stores-triage  (git-backed, materialised into the sandbox) │
   │                                                                    │
   │  1. analyse.py runs IN the sandbox and pulls its own record over   │
   │     Code Mode — get_part, get_consumption_log, get_vendor_lead_    │
   │     times — so the record never passes through the model           │
   │  2. four subagents dispatched at once, one tool call each          │
   │  3. adjudicate(): deterministic Python, four ordered rules         │
   │  4. raise_indent / send_vendor_mail carry destructiveHint → held   │
   └────────────────────────────────────────────────────────────────────┘
   │
   ├─ stores-mcp   remote HTTP MCP, bearer auth, 12 tools over Postgres
   ├─ Postgres     5 constitution tables + a run log
   └─ console      TrueForge event stream, keyed on threadId
```

`requireApprovalForTools` is narrowed to exactly the two irreversible tools. The
default (`["@write","@destructive"]`) would also hold `log_run`, so the agent
would sit waiting for permission to record that it had decided to do nothing —
and a gate that fires on everything trains the operator to click through it.

`askUserQuestions` is **disabled**. Left on, the agent reached the right decision
and then asked for permission in prose — no evidence, no payload, and no held
call for the harness to gate. That is the confirm() box this project exists to
replace, so the only route to a human is now calling the gated tool.

### The five things the harness is asked to prove, and where each one happens

| | where it happens |
|---|---|
| Real tools through MCP | `stores-mcp`, 12 tools over a real Postgres, remote HTTP with bearer auth |
| Generated code in a sandbox | `analyse.py` under bubblewrap; the sandbox installs pydantic and matplotlib from pypi itself |
| A pause before anything irreversible | `raise_indent` held, then `send_vendor_mail` held **separately** after approval |
| Work handed to subagents | four hypothesis subagents dispatched in parallel, one tool call each, four verdicts |
| A session that holds across reconnects | proved the hard way — a turn died mid-run on a rate limit and the session kept its four verdicts, so the rest was driven as a second turn and reached the gate |

That last row was not planned. Gemini's free tier allows five requests a minute
and four subagents dispatching at once is eight in ten seconds, so the turn died
about four requests short of the gate. The session survived it intact, which is
the feature working under exactly the conditions it exists for.

## Where TrueForge fits

We reimplemented none of it. The harness runs the agent loop, the MCP calls, the
sandbox, the parallel subagent threads, the approval pause and session
persistence. What we brought:

- `stores-mcp` — 12 tools over a real Postgres, remote HTTP with bearer auth
- the `stores-triage` skill — the procedure, plus the tested analysis script
- `adjudicate` — the deterministic decision
- an operator console driven by the harness event stream, keyed on `threadId`,
  which is what makes the four subagents legible as a board rather than a log

`requireApprovalForTools` is narrowed to exactly the two irreversible tools. The
default (`["@write","@destructive"]`) would also have held `log_run`, so the
agent would have sat waiting for permission to record that it had decided to do
nothing — a gate that fires on everything trains the operator to click through
it.

## What went wrong, honestly

- **Groq's free tier cannot host a TrueForge agent at all.** A bare agent sends
  67,358 tokens before we add anything; the free limit is 8,000 TPM. We measured
  that by reading the 413s rather than guessing, and it is not tunable — every
  feature toggle together saves ~1.5k.
- **Gemini Flash free tier is 20 requests/day**, which is roughly one full run
  per day. That shaped the whole design: the skill carries an explicit call
  budget and each subagent is allowed exactly one tool call.
- **The limit that actually bit was per-minute, not per-day.** Four subagents
  dispatching at once is eight requests in ten seconds, against a ceiling of
  five per minute, and the harness has no backoff — so the turn died mid-run
  every time, four requests short of the gate. We read that off the 429 itself
  (`limit: 5`) rather than assuming it was the daily quota again.

  | | Gemini free | OpenRouter `:free` |
  |---|---|---|
  | requests/minute | 5 | 20 |
  | requests/day | 20 | 50 |

  Moving to a free OpenRouter model is what let a run finish in one turn. Until
  then we drove it as two turns, which the session model supports because the
  verdicts survive a failed turn.
- **The local sandbox never had network, and we misdiagnosed it for three
  days.** The story was "the sandbox is offline, so stage wheels and set
  `PIP_NO_INDEX`". Both halves were wrong. The harness builds the sandbox's
  environment from scratch, so those variables never reached it and the
  wheelhouse was never consulted — and the sandbox is *supposed* to have
  network, since `pypi.org` is on the harness's own allowlist. The real fault:
  the sandbox reaches its filtering proxy over a Unix socket in `os.tmpdir()`,
  while the harness's Linux allow-read list omits `/tmp`. Nothing can connect,
  so `pip install pydantic` — the first thing a sandbox does — always fails, and
  skills fail with it because skills require a sandbox. Proved by driving the
  sandbox runtime's own CLI with the harness's exact filesystem policy:
  permissive gives HTTP 200, the real policy gives `Proxy CONNECT aborted`, the
  real policy plus `/tmp` gives 200 again. One variable, no model involved.
  Worked around without patching the dependency.
- **Three different "todays".** Postgres and the sandbox run on UTC, the host on
  IST, and they are on different dates for five and a half hours a day. Every
  date here is relative to Postgres `CURRENT_DATE`, but the analysis rebuilt its
  window from the local clock and adjudication compared ETAs against the host's.
  Since overdue consignments stopped counting as cover, that skew discards cover
  that is still valid — a demo recorded late in the evening could have flipped
  Run B into an indent and destroyed the contrast the whole thing rests on.
  There is one source of truth now.
- **Which model you pick decides whether the demo works at all.** The
  deterministic core does not care — `adjudicate` is tested code and Run B
  passes in CI with no model involved. But the *agent* has to actually follow
  the skill, and with identical skill text three free models did three different
  things: `minimax-m3` read `SKILL.md` and the scripts, then followed the
  procedure exactly; `glm-5-2` was upstream rate-limited within a second;
  `nemotron-3-ultra` ignored the skill outright — no subagents, no analysis
  script, no adjudication, just its own numpy script over evidence it had
  fetched itself. A model-selection finding, not a prompt one, and the argument
  for keeping the judgment in code.
- **Qodo found eleven real issues** across two PRs, zero false positives. Two
  would have broken the live run outright: the skill both forbade calling
  `raise_indent` before approval and told the agent to call it, so an obedient
  agent would never have created anything to approve; and the subagents were
  dispatched *before* the sandbox analysis whose output their verdicts had to
  carry — circular. Three were arithmetic: a p20 edge labelled p10, consumption
  rows counted as days, and a zero-stock divide-by-zero in the chart.
- **A day before the deadline** we found that `_lands_in_time` accepted ETAs in
  the past, so an overdue-but-still-in-transit consignment counted as cover —
  the agent would have recommended doing nothing while citing a delivery that
  never turned up. Found by rehearsing the whole pipeline with no model at all
  and reading the dates instead of the verdicts.

## Repo

- https://github.com/ANMOLGUPTA-24/stores-triage — MIT
- `notes/devlog.md` — what was built and what broke, every session
- `notes/trueforge-findings.md` — harness research, including measured context costs
- 65 Python tests, 32 TypeScript tests
