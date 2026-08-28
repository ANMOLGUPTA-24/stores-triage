# Demo video — word-for-word script

~3 minutes. Read it as written; it is timed. Beat IDs match
`notes/demo-storyboard.md`.

**Before you start:** check the database is in the state to film in (two
indents, empty run log — the check is in the storyboard), and close anything
with a key or a personal name in it. See the redaction list at the end.

---

## 0:00–0:25 · The problem

**Screen:** the live console at https://anmolgupta-24.github.io/stores-triage/
— the front door, both alert cards visible.

> A part drops below its reorder level at a locomotive works, and an alert
> fires. The stores officer now has to answer a question the alert cannot: is
> this real?
>
> The evidence lives in three systems that do not talk to each other — the
> consumption log, the open indents, and the consignments in transit. He gets
> twenty of these a day, about forty minutes each.
>
> Both mistakes cost. Raise a duplicate indent against stock already in transit
> and the works pays expedite rates on stock it already owns. Miss a real
> shortage and a locomotive sits idle.

*(point at the two cards)*

> These two alerts are the same problem from the outside. Nine days of stock
> against nine and a half. One is real. One is not.

---

## 0:25–1:05 · Run A, the investigation

**Screen:** click `TRB-4417`. Let the activity stream fill.

> This is the agent working. Every line is a real tool call against a real
> Postgres, through MCP.

*(when the four subagents appear — beat **A2**)*

> Four subagents, dispatched at once. Not four subtasks — four competing
> explanations for why this shortage might be on paper only. A consumption
> spike. Stock already inbound. A duplicate indent someone raised last week. A
> part being superseded.
>
> Every one of them is trying to prove the shortage is *not* real. Ruling all
> four out is what makes it real. This is differential diagnosis, not a task
> list.

*(when `sandbox provisioned` appears — beat **A3**)*

> And the arithmetic happens in a sandbox. Tested Python fits the draw rate,
> builds a lead-time distribution from what the vendor actually did, and solves
> the stockout date. No number in this system comes from the model.

---

## 1:05–1:45 · The gate

**Screen:** the dossier card. Let it sit. Do not scroll fast.

> Now the important part. The header has gone amber, and it says *blocked on
> you*.

*(**G2**, point at the sandbox line)*

> Four and a half units a day, runs dry in nine days, vendor takes thirty at the
> eightieth percentile. Those came out of the sandbox, not out of the model.

*(**G3**, the chart)*

> Which leaves that shaded stretch — three weeks with an empty bin before the
> vendor turns up. That gap is the argument for ordering now.

*(**G4**, scroll to the payload)*

> And this is the exact mail that will go out. Not a summary of it. The letter.

*(**G5**, the counterfactual)*

> With one line saying what would change its mind: if that unconfirmed
> consignment gets confirmed and lands in time, do not raise this indent.
>
> That is the whole idea. The agent never asks for permission bare. An approval
> is only worth something if a person can check it in five seconds.

*(click **Approve**)*

> Approve — and the indent is raised. Then it stops **again**, separately, for
> the vendor mail. Approving the order did not pre-approve the letter.

---

## 1:45–2:35 · Run B, the point

**Screen:** click `BRK-2290`.

> Second alert. Same shape, same shortfall, same nine days.

*(**B2** and **B3** as the verdicts land)*

> But this time two hypotheses come back positive. There is already an open
> indent, and there is a consignment in transit that lands before the stock runs
> out.

*(**B4**)*

> So the agent does nothing.
>
> Look at the screen: there is no amber anywhere, and there is no Approve
> button. Nothing to approve, because nothing should happen. And the run log
> records *no action* as an outcome — not as an error.
>
> This is the run I care about. Most agents cannot do this; they are built to
> act, so declining looks like failure. Being confidently right that nothing
> should happen is the harder half of the problem, and it is the half that saves
> the money.
>
> And it is trustworthy because it is not the model's opinion. Adjudication is
> ordinary Python with unit tests. This exact case passes in CI with no model
> involved at all.

---

## 2:35–3:00 · Where the harness fits

**Screen:** the run log, then the front door.

> TrueForge did the parts I did not have to build: the agent loop, the MCP
> calls, the sandbox, the parallel subagent threads, the approval pause, and the
> session — which mattered, because one run died mid-turn on a rate limit and
> came back with its four verdicts intact.
>
> What I brought is the tool server over Postgres, the skill, the analysis code
> that runs in the sandbox, and the adjudication — the part that decides.
>
> The agent's job is to gather evidence and call tools. The judgement is code
> you can read and test.

*(closing card)*

> You can drive both of these yourself, in a browser, in about a minute:
> **anmolgupta-24.github.io/stores-triage**

---

## Redaction check before you upload

- [ ] No API keys on screen — TrueForge settings closed
- [ ] Terminal scrollback cleared of any key or token
- [ ] `.env` not open in any editor
- [ ] Vendor addresses are the `.invalid` ones
- [ ] No personal email in any frame
- [ ] Browser tabs and bookmarks bar showing nothing personal

## Timing note

Read at a normal pace this runs about 2:50. If you are over three minutes, cut
the second half of the 2:35 section — the harness split is also in the README
and the write-up. Do **not** cut Run B.
