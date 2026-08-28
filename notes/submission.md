# Submission write-up — Stores Triage

Draft. Numbers are filled from the live runs, not from memory; anything still
written as ⟨…⟩ has not been measured yet.

---

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

**Run B returns `no_action`** — and the run log records that as an outcome, not
an error. There is no amber anywhere on the screen and no Approve button,
because nothing should happen. Most agent demos cannot do this; they are built
to act, so doing nothing looks like failure.

Being confidently right that nothing should happen is the harder half of the
problem, and it is the half that saves the money.

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
  per day. That shaped the whole design: the skill carries an explicit <20-call
  budget and each subagent is allowed exactly one tool call.
- **The sandbox has no network**, so `pip install` inside it fails. Fixed by
  staging wheels on the host and starting the harness with `PIP_NO_INDEX=1
  PIP_FIND_LINKS=…`.
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

- ⟨repo URL⟩ — MIT
- `notes/devlog.md` — what was built and what broke, every session
- `notes/trueforge-findings.md` — harness research, including measured context costs
- 55 Python tests, 32 TypeScript tests
