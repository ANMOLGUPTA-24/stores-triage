# Submission form — answers to paste

---

## What does your project do?
*(What problem does your project solve, and who is it for?)*

Stores Triage is for a stores officer at a locomotive works. A spare part drops
below its reorder level and an alert fires; he then has to answer a question the
alert cannot — is this real? The evidence lives in three systems that do not talk
to each other: the consumption log, the open indents, and the consignments in
transit. He gets twenty of these a day, about forty minutes each, so in practice
he either raises the indent to be safe or lets it sit.

Both mistakes cost. A duplicate indent against stock already in transit means the
works pays expedite rates on stock it already owns. A missed shortage idles a
locomotive.

The agent triages the alert and either raises the indent and mails the vendor —
behind a human approval gate — or concludes that nothing should happen, and shows
its working either way.

The demo is built on two alerts that are indistinguishable from the alert alone:
9.4 days of stock against 9.5. One is genuine. The other is already covered by an
open indent and a consignment in transit, and the agent correctly does nothing.
Most agents cannot do that; they are built to act, so declining looks like
failure. Being confidently right that nothing should happen is the harder half of
the problem, and it is the half that saves the money.

---

## How did you use TrueForge in your project?
*(Tell us what your agent does and how TrueForge fits into your project.)*

TrueForge runs everything about the agent; I did not reimplement any of it. It
handles the agent loop, the MCP calls, the sandbox, the parallel subagent threads,
the approval pause, and session persistence.

What I brought is the tool server, the procedure and the judgement:

- **stores-mcp** — 12 tools over a real Postgres, remote HTTP with bearer auth.
  `raise_indent` and `send_vendor_mail` carry `destructiveHint`, so the harness
  holds them.
- **The `stores-triage` skill** — the procedure, git-backed and materialised into
  the sandbox, plus the analysis script that runs there.
- **adjudicate()** — four ordered rules in ordinary Python with unit tests. The
  agent gathers evidence and calls tools; it does not get a vote on the answer.

All five capabilities the Best-Use criterion names are demonstrated:

| | where |
|---|---|
| Real tools through MCP | 12 tools over Postgres |
| Generated code in a sandbox | `analyse.py` under bubblewrap; it installs pydantic and matplotlib from pypi itself and pulls its own record over Code Mode, so the data never passes through the model |
| A pause before anything irreversible | `raise_indent` held, then `send_vendor_mail` held **separately** after approval |
| Work handed to subagents | four hypothesis subagents in parallel, one tool call each |
| A session that holds across reconnects | proved the hard way — a turn died mid-run on a rate limit and the session kept its four verdicts, so the rest was driven as a second turn and reached the gate |

Two configuration choices carry real design weight.
`requireApprovalForTools` is narrowed to exactly the two irreversible tools; the
default would also hold `log_run`, so the agent would wait for permission to
record that it had decided to do nothing, and a gate that fires on everything
trains the operator to click through it. And `askUserQuestions` is **disabled** —
left on, the agent reached the right decision and then asked for permission in
prose, with no evidence, no payload and no held call for the harness to gate.
That is the confirm() box this project exists to replace, so the only route to a
human is now calling the gated tool.

Both runs have been executed live: TRB-4417 holds at both gates (IND-2026-0732
raised on approval), BRK-2290 returns `no_action` in one unbroken 101-second turn.

---

## How did you use Qodo in your project?
*(Tell us how you used Qodo and how it improved the quality of your code.)*

Every substantive change went through a pull request reviewed by Qodo before
merge — nine PRs. The only non-merge commit on `main` is the initial scaffold.

Qodo raised **11 High-severity findings** (five on #3, five on #4, one on #7) and
**every one was fixed**; none was dismissed. Two would have broken the live demo
outright:

- **"Approval gate cannot start."** The skill both forbade calling `raise_indent`
  before approval *and* told the agent to call it so the harness would hold it. An
  obedient agent never creates anything to approve — the demo's central beat could
  not have fired.
- **"Gate instructions deadlock agent."** After I disabled the question tool, three
  places still said never to call the gated tools until a human had approved.
  Together that is a trap: present the dossier, wait for an approval that cannot
  exist, stop.

Three were arithmetic errors that would have put wrong numbers in front of an
operator: the stockout band solved with the p20/p80 cutoff while calling itself
p10/p90; consumption rows counted as days although the schema allows several
issues per date; and a zero-stock part dividing by a zero median, crashing on the
most urgent alert there is.

It also caught a defect in one of my own fixes, and a font size outside the type
tokens — which I fixed and widened, because patching only the flagged line would
have left six more the same commit had introduced.

I disagreed with exactly one Medium finding and wrote the reasoning on the PR
rather than silently ignoring it.

The habit it forced — small PRs, a review, a decision, a follow-up review —
is why the repo has 70 Python and 32 TypeScript tests plus an evaluation harness
that scores the adjudicator 16/16 on labelled scenarios and proves it has teeth by
breaking its own rules and checking it notices.

---

## Blog link

Publish `notes/blog-post.md` anywhere (dev.to, Hashnode, Medium) and paste the URL.
