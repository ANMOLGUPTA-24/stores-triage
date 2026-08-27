# Demo video storyboard

Three minutes, two runs, against §0b. Record Saturday evening, submit Sunday
morning. Every shot below has a source already working — nothing here needs to
be invented on the day.

Quota reality: Gemini Flash allows 20 model calls a day, and a full run costs
~15-18. **One live run per day.** So Run A and Run B are recorded on separate
days, or one is recorded live and the other replayed in the console. The console
replays a recorded event stream through the same reducer, so a replayed run is
not a mock-up — say so on camera rather than hiding it.

---

## 0:00-0:25 — the problem

Screen: the two alerts side by side in the console, before anything runs.

Say: a part drops below reorder level. Twenty of these a day, forty minutes each
across three systems. Raise a duplicate indent against stock already in transit
and the works pays expedite rates on stock it already owns. Miss a real shortage
and a locomotive sits idle.

Point at the two rows: **9.3 days and 9.4 days of stock left. From the alert
alone these are the same problem.** They are not.

## 0:25-1:05 — Run A, the investigation

Screen: activity stream on the left filling up, hypothesis board on the right.

Beats to show, in order:
- **A1** Tool calls landing in monospace — `get_part`, `get_consumption_log`
- **A2** **Four subagents appearing at once** on the board, each "investigating"
- **A3** `*** SANDBOX UP ***` in the stream
- **A4** Verdicts arriving: three negative, `inbound_delay` positive with CN-8821

Say: four competing explanations, one subagent each, running in parallel. Every
one of them is trying to prove the shortage is *not* real. Ruling all four out
is what makes it real. This is differential diagnosis, not a task list.

## 1:05-1:45 — Run A, the gate

Screen: the dossier card. Let it sit. Do not scroll fast.

Show, in this order:
- **G1** The header goes amber — **"blocked on you"** in the top bar at the same time
- **G2** The numbers, and say they came out of Python in the sandbox, not the model
- **G3** The chart — the ⟨gap⟩-day stretch with no stock, shaded, between running
  dry and the vendor delivering (the chart labels it; read the number off it)
- **G4** Scroll to the **full mail body**, verbatim, not a summary
- **G5** The counterfactual: *"if CN-8821 is confirmed and lands by ⟨CN-8821 ETA⟩,
  do not raise this indent"*

Say: the harness gives us the pause. The dossier is ours. An approval is only
worth anything if the human can check it in five seconds — so the gate carries
the queries, the code, the numbers, the exact payload, and the one line that
would change the answer.

Then click **Approve**. Indent raised, vendor mailed, logged.

## 1:45-2:35 — Run B, the point

Screen: second alert. Same shape.

Say up front: this one looks identical. Same shortfall, same ten days.

Beats:
- **B1** Same four subagents dispatched
- **B2** `duplicate_indent` **positive** — IND-2026-0731, raised seven days ago
- **B3** `inbound_delay` **positive** — CN-9104, in transit, lands ⟨CN-9104 ETA⟩
- **B4** Recommendation: **no action**

Point at the screen and say: **there is no amber anywhere, and no Approve
button.** Nothing to approve, because nothing should happen. The run log records
"no action" as an outcome, not an error.

Say: the reason this is trustworthy is that the decision is not the model's
opinion. `adjudicate` is deterministic code with unit tests, including this
exact case. Run B passes in CI without a model involved at all.

## 2:35-3:00 — where the harness fits

Say, over the run log:
- TrueForge runs the loop, the MCP calls, the sandbox, the subagent threads and
  the approval pause. We did not reimplement any of it.
- Our MCP server is a real server over a real Postgres.
- The numbers come from tested Python in the sandbox.
- The two irreversible tools carry `destructiveHint`, so the harness holds them.

Close on: the agent's job is to gather evidence and call tools. The maths and
the judgment are code you can read and test.

---

## Before recording

Every date in this script is written as ⟨placeholder⟩ on purpose. The seed is
`CURRENT_DATE`-relative, so the ETAs are whatever the database says on the day
you record. Read them off the screen; do not read them off this page.

- [ ] **Re-seed the database.** `docker compose down -v && docker compose up -d --wait`
      The seed is CURRENT_DATE-relative but fixed at volume-creation time, so an
      old volume shows consignment ETAs in the past — CN-8821 "due" a date that
      has already gone by reads badly on camera and changes what the agent says.

      This is what protects beats **A4**, **G5** and **B3** specifically: all
      three name a consignment ETA out loud, and an overdue ETA does not just
      look stale — since `_lands_in_time` stopped counting overdue stock as
      cover, a stale volume flips **B3** and turns Run B into an indent, which
      destroys the whole Run A / Run B contrast the video is built on.
- [ ] Confirm both runs still reach the right verdict after re-seeding
- [ ] Read the live ETAs out of the database and fill in the ⟨placeholders⟩
      (the ⟨gap⟩ in G3 is printed on the chart itself):
      `docker exec stores-triage-db psql -U stores -d stores -c \
       "select consignment_no, eta, status from consignments;"`

## Redaction checklist, before recording

- [ ] No API keys on screen — TrueForge Settings tab closed
- [ ] Terminal scrollback cleared of any key or token
- [ ] `.env` not open in any editor
- [ ] Vendor addresses are the `.invalid` ones
- [ ] No personal email in any frame
- [ ] Browser tabs and bookmarks bar not showing anything personal

## Footage already captured

- Console empty state, both runs, gate held, Run B "no action" — screenshots
- Chart PNG for TRB-4417, generated by `analyse.py`
- Live harness log showing the gate holding against real tools
EOF
