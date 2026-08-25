# CLAUDE.md — project constitution

Read this fully at the start of every session. If a request in this repo
conflicts with anything here, say so before writing code.

---

## 0. The project

**Name:** Stores Triage — an evidence-first agent for spare-part stock alerts.

- **WHO**
  A stores officer at a locomotive works. When a stock alert fires he decides,
  that morning, whether to raise a fresh indent on a vendor. He works across an
  inventory system, an indent register, and a mail thread with the vendor, and
  he has twenty of these a day.

- **THE ONE JOB**
  A part drops below reorder level. Decide whether this is a *genuine* shortage
  or a *paper* shortage — stock already in transit, a duplicate indent someone
  raised last week, or a consumption spike that was a one-off overhaul — and if
  genuine, raise the indent and mail the vendor.

- **WHAT IT COSTS TODAY**
  ~40 minutes per alert across three systems. The expensive failure is a
  duplicate indent raised against a consignment already in transit: the works
  pays expedite rates on stock it already owns. The other direction is worse —
  a missed genuine shortage idles a locomotive.

- **THE IRREVERSIBLE ACTION**
  Raising the indent and sending the vendor mail. Approval-gated, always.

- **THE REAL TOOL**
  Postgres MCP over a seeded schema: `parts`, `consumption_log`,
  `open_indents`, `consignments`, `vendor_lead_times`. Gmail or Slack MCP for
  the vendor mail and the notification. Synthetic seed data only — never real
  employer data, in the repo or the video.

- **THE SANDBOX WORK**
  The agent writes and runs Python that fits a consumption rate from the log,
  builds a lead-time distribution from historical vendor performance, projects
  a stockout date with an uncertainty band, and renders a chart. The numbers in
  the dossier come from this code — never from the model's own estimate.

## 0a. The idea that makes this different

**The agent never asks for permission bare.** An approval is only meaningful if
the human can check the reasoning in five seconds. So every gate carries a
**dossier**: the queries run, the code written, the numbers returned, the chart,
the exact payload that will be sent, and one line stating *what would change the
recommendation*.

**Subagents are hypotheses, not subtasks.** Spawn one per competing explanation —
`consumption_spike`, `inbound_delay`, `duplicate_indent`, `bom_change` — each
investigating independently and returning a verdict plus its evidence. The parent
adjudicates between them. This is differential diagnosis, not a work queue. Do
not refactor it into a pipeline of steps.

## 0b. The demo script

Three minutes, two runs. This is the definition of done for the whole project.
Anything not on this list does not get built.

**Run A — genuine shortage**
1. Stock alert arrives for a part below reorder level
2. Agent queries Postgres read-only: stock, consumption log, open indents, consignments
3. Four hypothesis subagents dispatched; each returns a verdict with evidence
4. Agent writes Python in the sandbox: consumption fit, lead-time distribution,
   projected stockout date + chart
5. Adjudication: genuine shortage, stockout in ~9 days, no inbound cover
6. **STOPS** — dossier card, full indent payload shown, "if consignment 8821
   lands by Thursday, don't do this"
7. Human approves → indent raised, vendor mailed, run logged

**Run B — looks identical, agent says do nothing**
8. Second alert, same shape
9. `duplicate_indent` and `inbound_delay` subagents both return positive
10. Agent recommends **no action**, with the consignment record as evidence.
    Nothing to approve, because nothing should happen.

Run B is the point of the whole demo. It is the proof the logic is real. Never
cut it for time.

---

## 1. What this project is

An agent built on **TrueForge** (TrueFoundry's open-source agent harness) for
the WeMakeDevs Agent Harness Hackathon. Submission: **30 Aug 2026, 20:00
London**. Public repo, buildable by a stranger, MIT licensed.

TrueForge runs the agent loop, the MCP tool calls, the sandbox, the approval
pause, the subagents, and session persistence. **We do not reimplement any of
that.** If you find yourself writing a tool-dispatch loop, a retry wrapper, a
subagent scheduler, or a sandbox runner, stop — the harness has it, and
hand-rolling it costs us the sponsor-tools criterion.

## 2. Hard rules

These map directly to how this is judged. Treat them as compile errors.

1. **No mocks on the tool path.** Seeded synthetic data in a real Postgres is
   fine; a Python dict pretending to be a database is not. Never write a
   function returning hardcoded results with `# TODO: connect real API` above it.
2. **Numbers come from the sandbox, never from the model.** If a figure appears
   in the dossier, there is code in the repo that computed it. No LLM-estimated
   quantities anywhere.
3. **The gate is a dossier, not a confirm().** Full payload, evidence, and the
   what-would-change-my-mind line, every time.
4. **Both runs, one job.** No settings pages, no auth, no multi-tenancy, no
   second domain. Push back if I ask for scope outside §0b.
5. **Small PRs, never straight to main.** Branch, PR, Qodo review, fix what it
   finds before merging; if we disagree with a finding, reply on the PR saying
   why. The trail is judged and cannot be faked on the last day.
6. **No secrets, no personal data, no employer data** in repo, commits, README,
   or video. `.env.example` only.

## 3. UI spec

Judged on whether a stranger could pick it up and drive it. Four surfaces,
nothing else:

- **Live activity stream** — what the agent is doing now. Tool name, arguments,
  result. Tool calls and sandbox output in monospace, visually distinct from
  the agent's prose.
- **Hypothesis board** — the four subagents side by side, each showing
  investigating → verdict → evidence. This is what makes the reasoning legible
  on camera.
- **Dossier / approval card** — impossible to miss. Recommendation, the four
  verdicts, the chart, the exact payload, the what-would-change-my-mind line,
  Approve / Reject. The interface must make it obvious the system is *blocked*
  on the human.
- **Run log** — what it did, in order, timestamped, re-readable afterwards.
  Run B ends here with "no action taken" as a first-class outcome, not an error.

Visual constraints, non-negotiable:
- One accent colour, used only for the blocked-on-human state. Everything else neutral.
- No gradients, no glassmorphism, no emoji as icons, no rounded-2xl card soup.
- Dense over airy. Operator console, not landing page.
- One display size, one body size, one mono size.
- Build the empty state and the waiting state — they are most of the demo.

## 4. Working style

- **Plan before building.** Anything beyond a one-file change: plan first, wait
  for approval. Say which files you will touch and what you will not touch.
- **Ask instead of assuming.** Missing detail → one direct question. Never fill
  a gap with a plausible default.
- **State uncertainty.** Unsure whether an MCP server supports something? Say
  so rather than writing hopeful code.
- **No speculative abstraction.** No base classes, plugin systems, or config
  layers for a one-week project.
- **Tests where logic lives.** The adjudication logic and the consumption/
  lead-time maths get unit tests, including the Run B case. UI does not.
- **README as you go.** Any PR that changes setup updates the README in the
  same PR.

## 5. Definition of done for any PR

- [ ] Runs on a clean clone with only `.env.example` filled in
- [ ] No stubs, no dead code, no commented-out blocks
- [ ] Qodo review addressed
- [ ] README still accurate
- [ ] Advances a beat in §0b — if it doesn't, it shouldn't exist

## 6. Out of scope (do not build, do not suggest)

User accounts · role management · billing · theme toggle · onboarding flows ·
a second domain · a plugin architecture · a generic "rules engine" ·
anything that ships after §0b is complete

## 7. Capture as you go (for the demo video and write-up)

Both are required at submission and neither can be reconstructed on the last
day, so material gets captured while it happens.

**Record screen clips the moment a beat first works**, not after polish: the
first successful tool call, the first sandbox chart, the first time the gate
holds, the first Run B "no action". Raw footage of a working beat is what the
demo is cut from — re-staging it on Sunday wastes hours and looks staged.

**Keep `notes/devlog.md` short.** After each session: what was built, what
broke. Two lines. Its only job is to make the submission write-up an editing
task instead of a writing task.

**The demo video** is ~3 minutes: the problem, the agent working end to end,
and where the harness fits. Storyboard it Saturday against §0b, record Saturday
evening, submit Sunday morning — not Sunday night.

Redact before recording: no keys on screen, no real vendor or employer names,
no personal data in any frame.
